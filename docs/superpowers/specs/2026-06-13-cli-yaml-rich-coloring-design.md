# Rich coloring for YAML output (CLI) — design

**Issue:** #13 — [CLI] Rich Coloring for YAML Output
**Status:** approved (grilled 2026-06-13)

## Goal

In a generated CLI, `--output yaml` prints plain text while `--output json` is
syntax-colored via rich. Color terminal YAML **consistently with JSON, through a
single shared mechanism**, with zero change to piped/redirected output.

## Current state

`<package>/_generated/output.py` (template `output.py.jinja`):
- JSON: `_console.print_json(data=data)` — rich-colored on a TTY, plain off-TTY.
- YAML: `_console.out(yaml.safe_dump(data, sort_keys=False, default_flow_style=False), highlight=False, end="")` — always plain.
- `config show` (`config_commands.py.jinja`) emits YAML via
  `typer.echo(yaml.safe_dump(effective_dict(), sort_keys=False, default_flow_style=False), nl=False)` — always plain, and not even through the rich `_console`.

rich has no `print_yaml`; the equivalent of the JSON path is `rich.syntax.Syntax`.

## Design

### Single mechanism: `output.print_yaml(text)`

Add to `output.py.jinja`:

```python
from rich.syntax import Syntax

def print_yaml(text: str) -> None:
    """Emit YAML to the console — syntax-highlighted on a terminal, byte-clean
    plain YAML when piped/redirected/NO_COLOR (rich strips styling off-TTY)."""
    _console.print(
        Syntax(
            text.rstrip("\n"),
            "yaml",
            theme="ansi_dark",
            background_color="default",
            word_wrap=False,
            line_numbers=False,
        )
    )
```

- `theme="ansi_dark"` → maps tokens to the 16 ANSI colors, respecting the
  terminal palette (consistent with how `print_json` uses console colors);
  `background_color="default"` → transparent, matching `print_json`'s
  no-background look.
- `word_wrap=False`, `line_numbers=False` → output stays copy-paste-clean.
- `text.rstrip("\n")` + `_console.print`'s single trailing newline ⇒ exactly one
  trailing newline (preserves `test_yaml_output_has_no_trailing_blank_line`).
- Off-TTY (`CliRunner`, pipes, redirects, `NO_COLOR`): rich emits no ANSI ⇒ plain
  valid YAML.

### Call sites (serialization unchanged — same `safe_dump` options)

- `output.render()` YAML branch:
  ```python
  if fmt == "yaml":
      print_yaml(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
      return
  ```
- `config_commands.config_show()` — replace the `typer.echo(..., nl=False)` with:
  ```python
  from . import output as _output
  ...
  _output.print_yaml(
      yaml.safe_dump(_config.effective_dict(), sort_keys=False, default_flow_style=False)
  )
  ```

### Import graph

`config_commands → output` is acyclic: `output` imports `config` + `diagnostics`;
`config` imports only `diagnostics`; neither imports `config_commands`. Adding
`from . import output` to `config_commands` introduces no cycle.

## Behavior / invariants

- **TTY:** both `--output yaml` and `config show` are syntax-highlighted.
- **Non-TTY / `NO_COLOR`:** byte-identical to today's plain output — no ANSI,
  exactly one trailing newline, `yaml.safe_load` round-trips to the same data
  (keeps `… --output yaml > file.yaml` and `config show | …` valid).
- Works within the existing `maybe_paged` pager context (rich pager,
  `styles=True`).
- Empty/`None` result: `render()` still returns early (no output).

## Out of scope

- Dry-run request bodies (JSON path, unchanged).
- Any non-YAML output; no new flags; no change to default-format selection.

## Testing (behavioral, through the emitted package — `tests/test_cli_emitted.py` `emitted` fixture)

1. Keep `test_yaml_output_has_no_trailing_blank_line`.
2. `--output yaml` colored on a terminal: render with a forced-terminal console
   (so `is_terminal` is true) → output contains ANSI SGR escapes (`\x1b[`).
3. `--output yaml` piped (default `CliRunner`, non-TTY): **no** ANSI, ends with
   exactly one newline, `yaml.safe_load(output)` equals the source data.
4. `config show` piped: no ANSI, content byte-identical to the pre-change plain
   dump, `yaml.safe_load` round-trips.
5. `config show` colored on a forced terminal: contains ANSI.

Force the terminal explicitly in the colored cases (don't rely on ambient color —
CI sets `FORCE_COLOR`, local doesn't; tests must be deterministic either way).
Run the offline gate (`uv run nox`) — lint/type/tests/docs green.

## Plan / review

After this spec: expert review (default `python-pro`), then `writing-plans`, then
`subagent-driven-development` on `feature/yaml-rich-coloring` (PR `--base
develop`, no version bump). Implements #13.
