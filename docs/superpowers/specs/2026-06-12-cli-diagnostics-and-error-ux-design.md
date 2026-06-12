# Generated CLI: Unified Diagnostics + Enriched Input Errors — Design

**Date:** 2026-06-12
**Status:** Approved design (grilled with user; all decisions below are user-confirmed)
**Scope:** phantasos CLI generator (`src/phantasos/generator/cli/`) — emitted into every generated CLI; validated on prisma-browser-cli.
**Origin:** A user hit an unhelpful invalid-JSON error on `create application private --urls "pb.example.com,pb2.example.com"`. Discovery in `docs/research/2026-06-12-json-flag-error-ux.md` (Option A chosen). The fix is generalized into a uniform diagnostics scheme.

## Motivation

The generated CLI emits warnings/errors through **three inconsistent mechanisms** —
`print(..., file=sys.stderr)` (6 sites), `typer.echo(..., err=True)` (4 sites), and Rich
`_err_console.print` (2 sites) — with two ad-hoc prefix conventions (`error:` / `warning:`),
**no icons, no shared theme, and no `NO_COLOR`/TTY handling** on the plain-`print` paths.
Separately, invalid JSON to a JSON-string flag (`--urls`, `--spec`) produces a one-line
message with no shape, example, or constraints.

This design introduces one **diagnostics facade** (icons + uniform format + correct
stream/exit discipline) emitted into every generated CLI, migrates all existing
error/warning sites onto it, and uses it to deliver **enriched input errors** (Option A)
that show the expected shape, an auto-derived example, and the bad value.

## Decisions (user-confirmed)

| Topic | Decision |
|---|---|
| Mechanism | **Hybrid facade.** Console sink = our own Rich rendering (NOT `RichHandler`). File sink = stdlib `logging` + `RotatingFileHandler`, **deferred to a future feature**, consuming the same record. Build the facade + console + record now; file backend drops in later without touching call sites. |
| Line format | `✖ error:` / `⚠ warning:` / `ℹ info:` — icon + lowercase level word + `: ` + message. Colors: error=red, warning=yellow, info=blue. |
| Levels | `error`, `warning`, `info` (numeric values aligned to stdlib `logging`: 40/30/20, so the future logging integration is seamless). |
| Streams | All diagnostics → **stderr**. stdout reserved for machine-consumable results (command JSON/YAML/table, `config show` body, `--version`, `--dry-run` preview). Confirmations (`wrote config.yml`, `merged from`) reclassify to `info` on stderr. |
| Degradation | Adaptive: icon + color when stderr is a TTY, color enabled, and the glyph is encodable. Otherwise plain `error: <msg>` (no icon, no color). Honors `NO_COLOR`; encoding-safe. |
| Multi-line | Primary line, then hanging-indented continuation lines with light labels (`expected:` / `example:` / `got:`), dim-styled. Carried as **structured fields** on the facade call (so the future file log stores them; styling stays uniform). |
| Refactor scope | All ~13 emitted-CLI diagnostic sites migrate, incl. the `SystemExit('error: …')` and `typer.echo(err=True)` ones; `render_error`'s HTTP-API path folds onto the facade. Generator build-time warnings (host-side) are OUT. |
| Exit codes | `0` success; `2` usage/input (bad flag value, invalid JSON, invalid `--columns`, file-exists, history-not-found); `1` runtime/operational (SDK/API failure, file-write failure). Facade only renders; callers exit via `fail(msg, code)`. |
| Option A | Enrich in `_build_body` (runtime; model in scope). Body json flags only (query json flags out). Required-only example. Fields: `expected` / `example` / `got`. Generic placeholder values (`"string"`/`false`). |
| Verbosity | New global `--quiet`/`-q` (errors always; suppresses info+warning) on generated verb commands, passed to `run()` → `diagnostics.set_min_level(...)`. `--verbose` unchanged; future home for debug + file log. |
| Module | New generated `_generated/diagnostics.py` owns the stderr console + theme + facade + `render_error`. `output.py` keeps result rendering and imports diagnostics. |
| Testing | Behavioral through the emitted fixture (CliRunner) asserting stderr + exit code with `NO_COLOR=1` for stable text; a few forced-TTY/`NO_COLOR` styling checks; one real-SDK test for the enriched json error; update existing message oracles. |

## Architecture & file map

All new/changed runtime code lives in the emitted `_generated/` (wiped + re-emitted every
build; users never edit it):

```
<pkg>/_generated/
  diagnostics.py     NEW      stderr console + theme + level model + emit/error/warning/info/fail
                              + render_error (SDK/HTTP); set_min_level()
  output.py          EDIT     drop _err_console + render_error (moved to diagnostics); import
                              diagnostics for the --columns error; result rendering stays
  runtime.py         EDIT     InputError gains structured fields; _coerce raises them; _build_body
                              enriches json InputErrors (_describe_json_field); _fail_input + SDK
                              error path + "no operation" route through diagnostics; run() takes quiet
  history.py         EDIT     3 warnings → diagnostics.warning
  config.py          EDIT     load warnings → diagnostics.warning
  config_commands.py EDIT     init errors → diagnostics.fail; "wrote"/"merged from" → diagnostics.info
  cli_commands.py    EDIT     history errors → diagnostics.fail; corrupt-lines/empty → warning/info
  commands.py.jinja  EDIT     inject --quiet/-q common option; pass quiet= to _rt.run
```

Generator side: `src/phantasos/generator/cli/render_cli.py` adds one `render(...)` call to
emit `diagnostics.py`; the generated-code lint test already covers it.

## `_generated/diagnostics.py` (new module)

### Level model + theme

```python
import enum
import sys
from typing import Any

from rich.console import Console
from rich.theme import Theme


class Level(enum.IntEnum):
    INFO = 20       # aligns with logging.INFO/WARNING/ERROR for the future file sink
    WARNING = 30
    ERROR = 40


_SPEC = {
    Level.ERROR:   ("error",   "✖", "diag.error"),
    Level.WARNING: ("warning", "⚠", "diag.warning"),
    Level.INFO:    ("info",    "ℹ", "diag.info"),
}

_THEME = Theme({
    "diag.error": "bold red",
    "diag.warning": "yellow",
    "diag.info": "blue",
    "diag.label": "dim",
})

_err_console = Console(stderr=True, theme=_THEME, highlight=False)

_min_level = Level.INFO  # mutated by set_min_level()


def set_min_level(level: Level) -> None:
    global _min_level
    _min_level = level
```

### Degradation + emit

`Console.is_terminal` is False when piped/redirected; Rich already drops color there and
honors `NO_COLOR`. Icons are gated additionally on glyph-encodability so a `LANG=C`
terminal never raises `UnicodeEncodeError`.

```python
def _styled() -> bool:
    return _err_console.is_terminal


def _icon(glyph: str) -> str:
    enc = getattr(sys.stderr, "encoding", None) or "utf-8"
    try:
        glyph.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return ""
    return glyph


def emit(level: Level, message: str, *, expected: str | None = None,
         example: str | None = None, got: Any | None = None,
         hint: str | None = None) -> None:
    if level < _min_level:
        return
    label, glyph, style = _SPEC[level]
    icon = _icon(glyph) if _styled() else ""
    prefix = f"{icon} " if icon else ""
    # markup=False so a message containing brackets/braces (JSON, JMESPath) is literal.
    if _styled():
        _err_console.print(f"{prefix}[{style}]{label}:[/] {message}", markup=True,
                           highlight=False)
    else:
        _err_console.print(f"{label}: {message}", markup=False, highlight=False)
    for lbl, val in (("expected", expected), ("example", example),
                     ("got", got), ("hint", hint)):
        if val is None:
            continue
        line = f"  {lbl}: {val}"
        if _styled():
            _err_console.print(f"[diag.label]{line}[/]", markup=False, highlight=False)
        else:
            _err_console.print(line, markup=False, highlight=False)
```

Note `markup=False` with a leading `[{style}]` is contradictory; the implementation uses
`_err_console.print(prefix, end="")` styled, then the message with `markup=False` — the plan
spells out the exact call sequence so a bracket-bearing message never triggers a
`MarkupError`. (See plan Task 1.)

### Public API

```python
def error(message: str, **kw: Any) -> None:   emit(Level.ERROR, message, **kw)
def warning(message: str, **kw: Any) -> None: emit(Level.WARNING, message, **kw)
def info(message: str, **kw: Any) -> None:    emit(Level.INFO, message, **kw)


def fail(message: str, *, code: int = 1, **kw: Any) -> "NoReturn":
    error(message, **kw)
    raise SystemExit(code)
```

### `render_error` (moved here from output.py, folded onto the facade)

HTTP/API errors (have `.status`) render a styled headline via `error(...)` then pretty-print
the JSON body with `_err_console.print_json`. Non-HTTP errors (ValidationError, anything
else) → `error(str(exc))`. The `_error_headline`/body-parsing helpers move with it.

## Option A — enriched input errors (`runtime.py`)

### `InputError` gains structured fields

```python
class InputError(Exception):
    def __init__(self, message: str, *, expected: str | None = None,
                 example: str | None = None, got: Any | None = None,
                 code: int = 2) -> None:
        super().__init__(message)
        self.message = message
        self.expected = expected
        self.example = example
        self.got = got
        self.code = code
```

### `_coerce` raises structured (basic) errors

- json decode fail → `InputError(f"{flag.name}: invalid JSON ({detail})", got=value)`
- bad int → `InputError(f"{flag.name}: invalid integer", got=value)`
- bad bool → `InputError(f"{flag.name}: invalid boolean (use true or false)", got=value)`

(`_coerce` has only the `Flag`, so it cannot add `expected`/`example` for json — that is
added in `_build_body`, which has the model.)

### `_build_body` enriches json flags from the model

A per-field coercion loop replaces the dict-comprehension; on `InputError` for a
`kind == "json"` flag it computes `expected` + `example` from the body model's field and
re-raises:

```python
def _describe_json_field(model_cls: Any, param: str) -> tuple[str | None, str | None]:
    """(expected, example_json) for a body model's json field, or (None, None)."""
    mf = getattr(model_cls, "model_fields", {}).get(param)
    if mf is None:
        return None, None
    ann = _strip_optional(mf.annotation)
    origin = typing.get_origin(ann)
    # count constraint (MinLen/MaxLen) for the "(1–100 items)" suffix
    lo = hi = None
    for m in getattr(mf, "metadata", []):
        lo = getattr(m, "min_length", lo)
        hi = getattr(m, "max_length", hi)
    if origin in (list, set):
        inner = _strip_optional(typing.get_args(ann)[0])
        is_obj = hasattr(inner, "model_fields")
        shape = "array of objects" if is_obj else "array"
        count = f" ({lo}–{hi} items)" if (lo and hi) else (
            f" (max {hi} items)" if hi else (f" (min {lo} items)" if lo else ""))
        ex = [_skeleton(inner)] if is_obj else [_placeholder(inner)]
        return f"a JSON {shape}{count}", json.dumps(ex)
    if hasattr(ann, "model_fields"):
        return "a JSON object", json.dumps(_skeleton(ann))
    return "a JSON object", json.dumps({"key": "value"})
```

with `_strip_optional`, `_placeholder` (`str→"string"`, `bool→False`, `int→0`, `float→0.0`,
else `None`), and `_skeleton(model)` = required, non-`additional_properties` fields keyed by
alias-or-name → placeholder. (Validated against the real SDK in the discovery doc.)

### `_fail_input` routes through diagnostics

```python
def _fail_input(exc: InputError) -> "NoReturn":
    _diag.fail(exc.message, code=exc.code,
               expected=exc.expected, example=exc.example,
               got=(repr(exc.got) if exc.got is not None else None))
```

Resulting render for the user's case:

```
✖ error: --urls: invalid JSON (Expecting value: line 1 column 1 (char 0))
  expected: a JSON array of objects (1–100 items)
  example: --urls '[{"url": "string"}]'
  got: 'pb.example.com,pb2.example.com'
```

## Refactor map (all emitted-CLI sites → facade)

| Site | Today | Becomes |
|---|---|---|
| `output.py:52` | `print("error: …", file=sys.stderr)` | (moves into `diagnostics.render_error`) |
| `output.py:75-79` | `_err_console.print("[bold red]…")` + JSON | `diagnostics.render_error` (HTTP branch) |
| `output.py:282-287` | `_err_console.print(..., bold red)` + `SystemExit(2)` | `_diag.fail(f"invalid --columns expression {path!r}: {exc}", code=2)` |
| `output.py:349` | `print("warning: pager command not found…")` | `_diag.warning(f"pager command not found: {argv[0]}")` |
| `history.py:51-55` | `print("warning: history file full…")` | `_diag.warning("history file full (… cap) — command not recorded")` |
| `history.py:63` | `print("warning: could not write history…")` | `_diag.warning(f"could not write history: {exc}")` |
| `history.py:74` | `print("warning: could not read history…")` | `_diag.warning(f"could not read history: {exc}")` |
| `config.py:211` | `print(f"warning: {w}")` | `_diag.warning(w)` |
| `cli_commands.py:30-31` | `typer.echo("error: no history entry…", err=True)` + `Exit(1)` | `_diag.fail(f"no history entry with id {entry}", code=2)` |
| `cli_commands.py:36` | `typer.echo("warning: skipped … corrupt…", err=True)` | `_diag.warning(f"skipped {corrupt} corrupt history line(s)")` |
| `cli_commands.py:38` | `typer.echo("history is empty")` (stdout) | `_diag.info("history is empty")` (stderr) |
| `config_commands.py:24-25` | `typer.echo("error: … exists…", err=True)` + `Exit(1)` | `_diag.fail(f"{path} exists (use --force to overwrite)", code=2)` |
| `config_commands.py:30-31` | `typer.echo("error: cannot write…", err=True)` + `Exit(1)` | `_diag.fail(f"cannot write {path}: {exc}", code=1)` |
| `config_commands.py:32` | `typer.echo(f"wrote {path}")` (stdout) | `_diag.info(f"wrote {path}")` (stderr) |
| `config_commands.py:44-45` | `typer.echo("# merged from: …")` (stdout) | `_diag.info(f"merged from: {', '.join(sources)}")` (stderr) |
| `runtime.py:136` | `SystemExit("error: no operation…")` | `_diag.fail(f"no operation for '{cmd.key}' matches the given arguments", code=2)` |
| `runtime.py:379-384` | `_history.record(...)` + `render_error` + `SystemExit(1)` | unchanged flow; `render_error` is now `_diag.render_error`; exit stays 1 |

**Left on stdout (results, outside the scheme):** command JSON/YAML/table output, `config show`
YAML body, `--version` (`app.py:27`), `--dry-run` preview (`output.py:131-132`, `runtime.py:203`).

## `--quiet`/`-q`

Injected as a common option on generated verb commands (mirrors `--verbose`), passed to
`_rt.run(..., quiet=quiet)`. `run()` calls `_diag.set_min_level(Level.ERROR if quiet else
Level.INFO)` at entry. **Not covered in v1** (recorded as follow-ups): `config`/`history` meta
sub-apps, and import-time config-load warnings (they fire before any flag is parsed).

## Error handling summary

- Diagnostics never raise; `fail()` renders then raises `SystemExit(code)`.
- `markup=False` on every message/continuation render → bracket/brace-bearing text
  (JSON, JMESPath, repr) never triggers Rich `MarkupError`.
- Stream discipline: errors/warnings/info → stderr; results → stdout. Pipe-safe.
- Encoding-safe: glyph dropped when stderr encoding can't encode it.

## Testing

Behavioral, through the emitted fixture (`tests/test_cli_emitted.py` `emitted` fixture) and
the real-SDK fixture (`tests/test_cli_emitted_real.py` `real_cli`). Assertions on `res.stderr`
+ `res.exit_code`, with `monkeypatch.setenv("NO_COLOR", "1")` for stable plain text. New tests:

1. `diagnostics.error/warning/info` plain format (`NO_COLOR`): `error: msg` / `warning: msg` / `info: msg` to stderr.
2. Styling on a forced terminal: icon `✖`/`⚠`/`ℹ` present; absent under `NO_COLOR`.
3. `set_min_level`/`--quiet`: `-q` suppresses info+warning, keeps error; default shows all.
4. Stream discipline: a warning lands on `res.stderr`, not `res.output`.
5. Enriched json error (fixture `--spec` + **real-SDK `--urls`**): stderr contains `expected:` / `example:` / `got:`, exit 2, `res.exception` is `SystemExit` (no traceback).
6. Exit codes: input error → 2; simulated SDK error → 1.
7. `render_error` HTTP path: styled headline + JSON body to stderr (migrated, still works).

Updated oracles (existing tests asserting old strings): `test_config_bad_bool_env_ignored`
(`config.py` warning), the history corrupt-line/not-found tests, and any asserting
`typer.echo` confirmations now on stderr.

## Out of scope (recorded for later)

- **File logging** (the hybrid's second sink): stdlib `logging` + `RotatingFileHandler`
  consuming the diagnostic record; the design memo's "rotating log file". Facade is built to
  accept it without call-site changes.
- **Model field-surface flag** — a generated-CLI flag to dump a body model's full field
  surface (all fields, required/optional, types) to the user; complements the required-only
  example. (Memory: `cli-gen-model-describe-flag`.)
- `--quiet` on meta sub-apps + import-time config warnings; a `configuration.quiet`/`log_level`
  config key; a `-v/-vv` debug ladder.
- Enriching query json flags and bool/int errors with `expected`/`example` (json body only for v1).
