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
        ),
        soft_wrap=True,
    )
```

- **`soft_wrap=True` is mandatory.** Off-TTY, `Console` falls back to width 80 and
  `Syntax` renders fixed-width segments that **crop** lines longer than the width
  (even with `word_wrap=False`) — silently truncating long YAML values (URLs,
  tokens, base64) and breaking the round-trip invariant. `soft_wrap=True` disables
  both wrapping and cropping while keeping colors on a TTY. (Verified against rich
  15.0.0 in all TTY/pipe × short/long-line cases.) NOTE: this is the one place the
  YAML path is NOT symmetric with JSON — `print_json` does not crop off-TTY, so
  the parity is "highlight-on-TTY / plain-off-TTY," achieved via different rich
  primitives; `soft_wrap` is what restores behavioral parity.
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

### Dependency

`Syntax` needs `pygments` (the `"yaml"` lexer). It resolves only transitively
today (rich depends on pygments), but the emitted CLI now imports a lexer
directly — make it explicit: add `"pygments>=2"` to `_CLI_DEPS` in
`src/phantasos/generator/cli/scaffold_context.py`. (Third file changed, alongside
`output.py.jinja` and `config_commands.py.jinja`.)

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

**Forcing color deterministically:** `_console` is built at import, so tests must
inject a terminal console rather than rely on ambient color (CI sets
`FORCE_COLOR`, local doesn't — relying on it fake-greens). Use the established
pattern (the diagnostics styled-icon test in `test_cli_emitted.py`):
`monkeypatch.setattr(<emitted>.output, "_console", Console(force_terminal=True, file=buf))`
— `print_yaml` reads the module global at call time, so this takes effect.

1. Keep `test_yaml_output_has_no_trailing_blank_line`.
2. **Colored on a terminal:** with a forced-terminal `_console`, `--output yaml`
   output contains ANSI SGR escapes (`\x1b[`).
3. **Piped (default `CliRunner`, non-TTY):** no ANSI, exactly one trailing
   newline, `yaml.safe_load(output)` equals the source data.
4. **Long-line round-trip (regression guard for the crop blocker):** a payload
   with a value far longer than 80 columns, piped → `yaml.safe_load(output)`
   equals the source (no truncation). Also exercise a list/nested payload.
5. **`config show` piped:** no ANSI; content byte-identical to the pre-change
   plain dump; `yaml.safe_load` round-trips. (`merged from: …` stays on stderr via
   `_diag.info`; the YAML goes to stdout — `CliRunner` mixes both into `.output`.)
6. **`config show` colored** on a forced terminal: contains ANSI.

Run the offline gate (`uv run nox`) — lint/type/tests/docs green.

## Plan / review

After this spec: expert review (default `python-pro`), then `writing-plans`, then
`subagent-driven-development` on `feature/yaml-rich-coloring` (PR `--base
develop`, no version bump). Implements #13.
