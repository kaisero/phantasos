# Generated CLI: Unified Diagnostics + Enriched Input Errors — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every generated CLI one diagnostics facade (icons + uniform `✖ error:` / `⚠ warning:` / `ℹ info:` format, correct stream/exit discipline) and use it to deliver enriched, example-rich input errors; migrate all existing ad-hoc `print`/`typer.echo`/`_err_console` error & warning sites onto it.

**Architecture:** A new generated module `_generated/diagnostics.py` owns the stderr Rich console, a theme, a level model, and `error()/warning()/info()/fail()` plus the migrated `render_error`. Console rendering is bespoke Rich (a future stdlib-`logging` file sink consumes the same record). `runtime.py` enriches JSON-flag `InputError`s from the body model. All ~13 existing diagnostic sites are rewritten to call the facade.

**Tech Stack:** Python 3.11+, Jinja2 templates, Rich, Typer, pydantic v2, pytest + Typer `CliRunner`.

**Design doc:** `docs/superpowers/specs/2026-06-12-cli-diagnostics-and-error-ux-design.md`
**Discovery:** `docs/research/2026-06-12-json-flag-error-ux.md`

**Test runner note:** the suite runs with `uv run python -m pytest …`. On this sshfs checkout, `.nox` venv creation fails, so prefix env to relocate: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest …`. The `emitted` fixture (fakesdk) and `real_cli` fixture (prisma-browser-sdk) already exist in `tests/test_cli_emitted.py` / `tests/test_cli_emitted_real.py`.

**Pre-flight corrections (python-pro review, 2026-06-12 — all empirically verified):**
- **`res.output` includes stderr** in click 8.4.1 (combined). So existing oracles that assert on `res.output` keep passing regardless of which stream a message moves to — do NOT repoint them to `res.stderr`. New tests may still assert on `res.stderr` for stream-specificity.
- **`runtime._error_headline_for` calls `_output._error_headline`** (runtime.py.jinja:218), which Task 2 deletes from `output.py`. Task 2 MUST repoint it to `_diag._error_headline`, or every recorded API error raises `AttributeError`.
- **`render_error`'s new headline drops the literal `Error ` prefix** (`error: 400 Bad Request — …`, not `Error 400 …`). Three existing tests assert `"Error 400 Bad Request"` — they must change to `"400 Bad Request"`: `tests/test_cli_emitted.py:733` (unit), `:770` (e2e), `tests/test_cli_emitted_real.py:379` (e2e). Plus `test_error_headline_extraction` (`:697`) must repoint `out._error_headline` → `diagnostics._error_headline`.
- **`NoReturn` must be imported** in `runtime.py.jinja` (it currently imports only `Any`) and the annotation written **unquoted** — the build auto-runs `ruff --fix` which strips the quotes, leaving an undefined name (F821) that fails the generated-lint gate.
- **Add `"quiet"` to `render_cli._RESERVED`** (line 25) alongside `verbose`/`pager`, so an SDK field named `quiet` can't collide with the injected option.
- **Remove `import sys` from `config.py.jinja`** after its only use (the migrated warning) is gone (F401).
- Diagnostic lines must stay **< ~80 chars** for contiguous-substring assertions (CliRunner stderr width is 80); assert on short stable fragments.

---

## File map

```
src/phantasos/generator/cli/templates/_generated/diagnostics.py.jinja   CREATE
src/phantasos/generator/cli/render_cli.py                                MODIFY (emit diagnostics.py)
src/phantasos/generator/cli/templates/_generated/output.py.jinja        MODIFY (drop _err_console + render_error; use diagnostics for --columns)
src/phantasos/generator/cli/templates/_generated/runtime.py.jinja       MODIFY (InputError fields, _coerce, _build_body enrich, _fail_input, SDK path, no-op route, run(quiet))
src/phantasos/generator/cli/templates/_generated/history.py.jinja       MODIFY (3 warnings)
src/phantasos/generator/cli/templates/_generated/config.py.jinja        MODIFY (load warnings)
src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja  MODIFY (history errors/warnings/empty)
src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja MODIFY (init errors + confirmations)
src/phantasos/generator/cli/templates/_generated/commands.py.jinja      MODIFY (inject --quiet, pass quiet=)
tests/test_cli_emitted.py                                               MODIFY (new behavioral tests + oracle updates)
tests/test_cli_emitted_real.py                                         MODIFY (real-SDK enriched-error test)
tests/test_cli_render.py                                               MODIFY (diagnostics.py emitted)
```

---

## Task 1: diagnostics module — core facade

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/diagnostics.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (the `render(...)` block ~line 318-325)
- Test: `tests/test_cli_render.py`, `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test (module is emitted)**

In `tests/test_cli_render.py`, add:

```python
def test_render_cli_emits_diagnostics_module(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    assert (tmp_path / "fakesdk_cli" / "_generated" / "diagnostics.py").exists()
```

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_render.py::test_render_cli_emits_diagnostics_module -q`
Expected: FAIL (file does not exist).

- [ ] **Step 3: Create the template**

Create `src/phantasos/generator/cli/templates/_generated/diagnostics.py.jinja`:

```python
"""Unified CLI diagnostics: icon + level + message to stderr (Rich), adaptive to
TTY/NO_COLOR/encoding. error/warning/info + fail() + render_error(). The console sink
is bespoke; a future stdlib-logging file sink can consume the same calls."""

from __future__ import annotations

import enum
import json
import sys
from typing import Any, NoReturn

from rich.console import Console
from rich.theme import Theme


class Level(enum.IntEnum):
    INFO = 20      # values align with logging.INFO/WARNING/ERROR for a future file sink
    WARNING = 30
    ERROR = 40


_SPEC: dict[Level, tuple[str, str, str]] = {
    Level.ERROR: ("error", "✖", "diag.error"),       # ✖
    Level.WARNING: ("warning", "⚠", "diag.warning"), # ⚠
    Level.INFO: ("info", "ℹ", "diag.info"),          # ℹ
}

_THEME = Theme({
    "diag.error": "bold red",
    "diag.warning": "yellow",
    "diag.info": "blue",
    "diag.label": "dim",
})

_err_console = Console(stderr=True, theme=_THEME, highlight=False)

_min_level = Level.INFO


def set_min_level(level: Level) -> None:
    global _min_level
    _min_level = level


def _styled() -> bool:
    # Plain when piped/redirected (not a TTY) or NO_COLOR/no-color is set.
    return _err_console.is_terminal and not _err_console.no_color


def _icon(glyph: str) -> str:
    enc = getattr(sys.stderr, "encoding", None) or "utf-8"
    try:
        glyph.encode(enc)
    except (UnicodeEncodeError, LookupError):
        return ""
    return glyph


def emit(level: Level, message: str, *, expected: str | None = None,
         example: str | None = None, got: str | None = None,
         hint: str | None = None) -> None:
    if level < _min_level:
        return
    label, glyph, style = _SPEC[level]
    if _styled():
        icon = _icon(glyph)
        head = f"{icon} {label}:" if icon else f"{label}:"
        # style= (not markup) colors the token while keeping the message literal,
        # so a bracket/brace-bearing message never trips Rich markup parsing.
        _err_console.print(head, end=" ", style=style, markup=False, highlight=False)
    else:
        _err_console.print(f"{label}:", end=" ", markup=False, highlight=False)
    _err_console.print(message, markup=False, highlight=False)
    for lbl, val in (("expected", expected), ("example", example),
                     ("got", got), ("hint", hint)):
        if val is None:
            continue
        _err_console.print(
            f"  {lbl}: {val}", markup=False, highlight=False,
            style=("diag.label" if _styled() else None),
        )


def error(message: str, **kw: Any) -> None:
    emit(Level.ERROR, message, **kw)


def warning(message: str, **kw: Any) -> None:
    emit(Level.WARNING, message, **kw)


def info(message: str, **kw: Any) -> None:
    emit(Level.INFO, message, **kw)


def fail(message: str, *, code: int = 1, **kw: Any) -> NoReturn:
    error(message, **kw)
    raise SystemExit(code)


def _error_headline(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for wrapper in ("errorResponse", "error_response"):
        if isinstance(data.get(wrapper), dict):
            data = data[wrapper]
            break
    if isinstance(data.get("error"), dict):
        data = data["error"]
    for key in ("error", "message", "detail", "title", "description"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def render_error(exc: Any) -> None:
    """SDK/API error -> stderr. HTTP errors (.status) get a styled headline + JSON body;
    everything else is a plain error line."""
    status = getattr(exc, "status", None)
    if status is None:
        error(str(exc))
        return
    reason = getattr(exc, "reason", "") or ""
    body = getattr(exc, "body", None)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    parsed: Any = None
    if isinstance(body, str) and body.strip():
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = None
    if parsed is None:
        data = getattr(exc, "data", None)
        if data is not None and hasattr(data, "model_dump"):
            try:
                parsed = data.model_dump(mode="json", by_alias=True, exclude_none=True)
            except Exception:
                parsed = None
    head = f"{status} {reason}".rstrip()
    headline = _error_headline(parsed)
    error(f"{head} — {headline}" if headline else head)
    if parsed is not None:
        _err_console.print_json(data=parsed)
    elif isinstance(body, str) and body.strip():
        _err_console.print(body.strip())
```

- [ ] **Step 4: Wire it into the generator**

In `src/phantasos/generator/cli/render_cli.py`, in the `render(...)` block (just before the `output.py` line), add:

```python
    render("_generated/diagnostics.py.jinja", gen / "diagnostics.py")
```

- [ ] **Step 5: Run the emission test — verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_render.py::test_render_cli_emits_diagnostics_module -q`
Expected: PASS.

- [ ] **Step 6: Write behavioral format + degradation + min-level tests**

In `tests/test_cli_emitted.py`, add:

```python
def test_diagnostics_plain_format_no_color(emitted):
    # Inject an explicit no_color StringIO console — the plain path needs no env/reload.
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    from rich.console import Console
    import io
    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, theme=d._THEME, no_color=True)
    d.set_min_level(d.Level.INFO)
    d.error("boom [x]")
    d.warning("careful")
    d.info("fyi")
    out = buf.getvalue()
    assert "error: boom [x]" in out      # bracket survives (markup off)
    assert "warning: careful" in out
    assert "info: fyi" in out
    assert "✖" not in out           # no icon when no-color


def test_diagnostics_styled_has_icon_on_terminal(emitted):
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    from rich.console import Console
    import io
    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, theme=d._THEME, force_terminal=True)
    d.set_min_level(d.Level.INFO)
    d.error("boom")
    assert "✖" in buf.getvalue()    # ✖ icon present on a terminal


def test_diagnostics_min_level_suppresses(emitted):
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    from rich.console import Console
    import io
    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, no_color=True)
    d.set_min_level(d.Level.ERROR)       # quiet
    d.warning("hidden")
    d.info("hidden")
    d.error("shown")
    out = buf.getvalue()
    assert "shown" in out and "hidden" not in out
    d.set_min_level(d.Level.INFO)        # reset for other tests
```

- [ ] **Step 7: Run them — verify pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py -k diagnostics -q`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/diagnostics.py.jinja \
        src/phantasos/generator/cli/render_cli.py \
        tests/test_cli_render.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emit _generated/diagnostics.py (icons + uniform error/warning/info to stderr)"
```

---

## Task 2: route SDK errors + --columns through diagnostics; retire output.py's error code

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/output.py.jinja` (remove `_err_console` def + `render_error` + `_error_headline`; rewrite the `--columns` error)
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (SDK-error path uses `_diag.render_error`; add `from . import diagnostics as _diag`)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test (render_error still works after move)**

```python
def test_render_error_http_via_diagnostics(emitted, monkeypatch):
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    from rich.console import Console
    import io
    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, no_color=True)

    class _Exc(Exception):
        status = 404
        reason = "Not Found"
        body = '{"error": {"message": "nope"}}'
    d.render_error(_Exc())
    out = buf.getvalue()
    assert "error: 404 Not Found — nope" in out
    assert "nope" in out
```

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_render_error_http_via_diagnostics -q`
Expected: FAIL (`render_error` not yet in diagnostics OR headline format differs) — it actually passes if Task 1 added `render_error`. If it passes, that's fine; proceed. If the existing `output.render_error` is what test imports elsewhere, continue to migrate.

- [ ] **Step 3: Remove the moved code from output.py**

In `output.py.jinja`: delete the `_err_console = Console(stderr=True)` line (keep `_console = Console()`), delete `_error_headline(...)`, delete `render_error(...)`. Add at the imports:

```python
from . import diagnostics as _diag
```

Rewrite the `--columns` error (the `except Exception as exc:` block around line 282) to:

```python
        except Exception as exc:  # jmespath.exceptions.JMESPathError and friends
            _diag.fail(f"invalid --columns expression {path!r}: {exc}", code=2)
```

Replace any remaining `_err_console` references in output.py with `_diag._err_console` (e.g. the dry-run helper uses `_console`, not `_err_console`, so likely none remain — grep to confirm).

- [ ] **Step 4: Point runtime at diagnostics.render_error**

In `runtime.py.jinja`: add `from . import diagnostics as _diag` near the other imports. In the SDK-error `except (_sdk_exc(), ValidationError) as exc:` block, change `_output.render_error(exc)` to `_diag.render_error(exc)`. **ALSO** repoint `_error_headline_for` (runtime.py.jinja:218): change `_output._error_headline(json.loads(body))` to `_diag._error_headline(json.loads(body))` — Task 2 Step 3 deletes it from `output.py`, and `_error_headline_for` is called by `_history_entry` on every error, so missing this throws `AttributeError` on all SDK errors. Update its docstring reference (`:210`) too.

- [ ] **Step 5: Run targeted + existing error tests, update all affected oracles**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py -k "render_error or columns or error or headline or pretty" -q`
Expected: PASS after updating these oracles (verified to reference the moved/renamed symbols):
- `test_render_error_non_api` / `test_render_error_api_exception_to_stderr` / `test_render_error_non_json_body` — repoint `out.render_error` import to `diagnostics.render_error`.
- `test_error_headline_extraction` (tests/test_cli_emitted.py:697) — repoint `out._error_headline` → `diagnostics._error_headline` (logic unchanged).
- `test_render_error_api_exception_to_stderr` (:733), `test_cli_runner_api_error_is_pretty` (:770), and `test_real_create_api_error_is_pretty` (tests/test_cli_emitted_real.py:379) — change `"Error 400 Bad Request"` → `"400 Bad Request"` (the new headline is `error: 400 Bad Request — …`; the redundant `Error ` prefix is gone now that the facade prints the `error:` label).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/output.py.jinja \
        src/phantasos/generator/cli/templates/_generated/runtime.py.jinja \
        tests/test_cli_emitted.py
git commit -m "refactor(cli-gen): move render_error + --columns error onto the diagnostics facade"
```

---

## Task 3: InputError structured fields + _coerce + _fail_input via diagnostics

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`InputError`, `_coerce`, `_fail_input`)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing test (bad bool routes through diagnostics, exit 2, no traceback)**

```python
def test_bool_error_uses_diagnostics_format(emitted, monkeypatch):
    from typer.testing import CliRunner
    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    res = CliRunner().invoke(main.app, ["create", "widget", "--name", "w",
                                        "--priority", "1", "--enabled", "maybe"])
    assert res.exit_code == 2
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "error: --enabled: invalid boolean" in res.stderr
    assert "got: 'maybe'" in res.stderr
```

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_bool_error_uses_diagnostics_format -q`
Expected: FAIL (today's message is `--enabled: invalid boolean 'maybe' (use true or false).`, no `got:` line, and not via diagnostics).

- [ ] **Step 3: Give InputError structured fields**

Replace the `class InputError(Exception):` block in `runtime.py.jinja` with:

```python
class InputError(Exception):
    """A user-supplied flag value could not be parsed. Carries optional structured
    fields rendered by the diagnostics facade; never a raw traceback."""

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

- [ ] **Step 4: Rewrite _coerce to attach `got` (and drop the trailing hint text)**

```python
def _coerce(flag: Flag, value: Any) -> Any:
    if value is None:
        return None
    if flag.kind == "json" and isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise InputError(f"{flag.name}: invalid JSON ({exc})", got=value) from exc
    if flag.py_type == "int" and isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise InputError(f"{flag.name}: invalid integer", got=value) from exc
    if flag.py_type == "bool" and isinstance(value, str):
        v = value.strip().lower()
        if v in _BOOL_TRUE:
            return True
        if v in _BOOL_FALSE:
            return False
        raise InputError(f"{flag.name}: invalid boolean (use true or false)", got=value)
    return value
```

- [ ] **Step 5: Route _fail_input through diagnostics**

First change runtime's typing import (it currently imports only `Any`) to:

```python
from typing import Any, NoReturn
```

Then (note: **unquoted** `NoReturn` — the build's `ruff --fix` strips quotes, so a quoted forward-ref would be left undefined and fail F821):

```python
def _fail_input(exc: InputError) -> NoReturn:
    _diag.fail(exc.message, code=exc.code,
               expected=exc.expected, example=exc.example,
               got=(repr(exc.got) if exc.got is not None else None))
```

- [ ] **Step 6: Run the test — verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_bool_error_uses_diagnostics_format -q`
Expected: PASS. Also re-run the existing `test_bool_body_flag_rejects_non_bool_value` and `test_invalid_json_flag_reports_clean_error`; update their assertions to the new `error:`/`got:` format.

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): InputError carries structured fields; coercion errors render via diagnostics"
```

---

## Task 4: Option A — enrich JSON-flag errors from the body model

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`_build_body` + helpers)
- Test: `tests/test_cli_emitted.py` (fixture `--spec`), `tests/test_cli_emitted_real.py` (real `--urls`)

- [ ] **Step 1: Write the failing real-SDK test**

In `tests/test_cli_emitted_real.py`:

```python
def test_private_application_invalid_urls_enriched(real_cli, monkeypatch):
    from typer.testing import CliRunner
    monkeypatch.setenv("NO_COLOR", "1")
    _patch_client(monkeypatch)
    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(main.app, [
        "create", "application", "private", "--name", "cli-application",
        "--urls", "pb.example.com,pb2.example.com",
        "--primary-url", "pb.example.com", "--route-to-prisma", "false"])
    assert res.exit_code == 2
    assert res.exception is None or isinstance(res.exception, SystemExit)
    err = res.stderr
    assert "error: --urls: invalid JSON" in err
    assert "expected: a JSON array of objects (1–100 items)" in err
    assert 'example: --urls \'[{"url": "string"}]\'' in err
    assert "got: 'pb.example.com,pb2.example.com'" in err
```

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted_real.py::test_private_application_invalid_urls_enriched -q`
Expected: FAIL (no `expected:`/`example:` lines yet). If `real_cli` skips (SDK absent), run the fixture variant in Step 6 instead.

- [ ] **Step 3: Add the describe helpers + per-field enriching loop to runtime.py.jinja**

Add helpers near `_build_body`:

```python
def _strip_optional(ann: Any) -> Any:
    if typing.get_origin(ann) is typing.Union:
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return ann


def _placeholder(ann: Any) -> Any:
    return {str: "string", bool: False, int: 0, float: 0.0}.get(_strip_optional(ann), None)


def _skeleton(model: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, f in model.model_fields.items():
        if name == "additional_properties" or not f.is_required():
            continue
        out[f.alias or name] = _placeholder(f.annotation)
    return out


def _describe_json_field(model_cls: Any, param: str) -> tuple[str | None, str | None]:
    mf = getattr(model_cls, "model_fields", {}).get(param)
    if mf is None:
        return None, None
    ann = _strip_optional(mf.annotation)
    origin = typing.get_origin(ann)
    lo = hi = None
    for m in getattr(mf, "metadata", []):
        lo = getattr(m, "min_length", lo)
        hi = getattr(m, "max_length", hi)
    if origin in (list, set):
        inner = _strip_optional(typing.get_args(ann)[0])
        is_obj = hasattr(inner, "model_fields")
        shape = "array of objects" if is_obj else "array"
        if lo and hi:
            count = f" ({lo}–{hi} items)"
        elif hi:
            count = f" (max {hi} items)"
        elif lo:
            count = f" (min {lo} items)"
        else:
            count = ""
        ex = [_skeleton(inner)] if is_obj else [_placeholder(inner)]
        return f"a JSON {shape}{count}", json.dumps(ex)
    if hasattr(ann, "model_fields"):
        return "a JSON object", json.dumps(_skeleton(ann))
    return "a JSON object", json.dumps({"key": "value"})
```

Replace the first line of `_build_body` (`parsed = {k: _coerce(...) ...}`) with a loop:

```python
    model_cls = getattr(models, binding.body_model, None)
    fields = getattr(model_cls, "model_fields", {}) if model_cls else {}
    parsed: dict[str, Any] = {}
    for k, v in body.items():
        if v is None:
            continue
        try:
            parsed[k] = _coerce(flags[k], v)
        except InputError as exc:
            if flags[k].kind == "json" and exc.expected is None:
                exp, ex = _describe_json_field(model_cls, k)
                exc.expected, exc.example = exp, (f"{flags[k].name} '{ex}'" if ex else None)
            raise
```

(Leave the rest of `_build_body` — `extra`, `model_construct` vs `model_cls(**parsed)`, wrapper — unchanged, **except** delete the now-duplicate `model_cls = getattr(models, binding.body_model)` line further down: the loop above already binds `model_cls`.)

- [ ] **Step 4: Run the real-SDK test — verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted_real.py::test_private_application_invalid_urls_enriched -q`
Expected: PASS (or SKIP if SDK absent — then rely on Step 6).

- [ ] **Step 5: Add the fixture-level test (`--spec` dict json flag) so coverage survives without the SDK**

In `tests/test_cli_emitted.py`:

```python
def test_invalid_json_flag_enriched(emitted, monkeypatch):
    from typer.testing import CliRunner
    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    res = CliRunner().invoke(main.app, ["create", "widget", "--name", "w",
                                        "--priority", "1", "--spec", "notjson"])
    assert res.exit_code == 2
    assert "error: --spec: invalid JSON" in res.stderr
    assert "expected: a JSON object" in res.stderr     # spec is a dict field
    assert "got: 'notjson'" in res.stderr
```

- [ ] **Step 6: Run both — verify pass**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_invalid_json_flag_enriched tests/test_cli_emitted_real.py::test_private_application_invalid_urls_enriched -q`
Expected: PASS (real one may SKIP).

- [ ] **Step 7: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja \
        tests/test_cli_emitted.py tests/test_cli_emitted_real.py
git commit -m "feat(cli-gen): enrich JSON-flag errors with expected shape + auto example (Option A)"
```

---

## Task 5: migrate remaining warning/error sites + reclassify confirmations

**Files:**
- Modify: `history.py.jinja`, `config.py.jinja`, `output.py.jinja` (pager), `cli_commands.py.jinja`, `config_commands.py.jinja`, `runtime.py.jinja` (the "no operation" SystemExit)
- Test: `tests/test_cli_emitted.py` (representative sites + oracle updates)

- [ ] **Step 1: Write the failing test (a warning uses the new format on stderr)**

```python
def test_config_bad_bool_env_diagnostics(emitted, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "banana")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    cfg.get()
    err = capsys.readouterr().err
    assert "warning: " in err and "not a boolean" in err
    assert "✖" not in err  # plain under NO_COLOR
```

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_config_bad_bool_env_diagnostics -q`
Expected: FAIL (today emits `warning: {w}` via plain `print`; assertion on format/behavior differs once routed through diagnostics — verify it fails meaningfully, else keep as a guard).

- [ ] **Step 3: Migrate each site**

In each template add `from . import diagnostics as _diag` (history.py, config.py already import siblings; follow the existing import style) and rewrite:

- `history.py.jinja`: the three `print("warning: …", file=sys.stderr)` →
  `_diag.warning("history file full (… cap) — command not recorded")`,
  `_diag.warning(f"could not write history: {exc}")`,
  `_diag.warning(f"could not read history: {exc}")`. Remove now-unused `sys` import if nothing else uses it.
- `config.py.jinja:211`: `for w in warnings: _diag.warning(w)` (was `print(f"warning: {w}", file=sys.stderr)`). Then **remove `import sys`** from config.py.jinja — it has no other use, so it would fail F401.
- `output.py.jinja:349` (pager): `_diag.warning(f"pager command not found: {argv[0]}")`.
- `cli_commands.py.jinja`: `:30` → `_diag.fail(f"no history entry with id {entry}", code=2)` (drop the `typer.Exit(1)` line); `:36` → `_diag.warning(f"skipped {corrupt} corrupt history line(s)")`; `:38` → `_diag.info("history is empty")`.
- `config_commands.py.jinja`: `:24` → `_diag.fail(f"{path} exists (use --force to overwrite)", code=2)` (drop the Exit line); `:30` → `_diag.fail(f"cannot write {path}: {exc}", code=1)`; `:32` → `_diag.info(f"wrote {path}")`; `:44-45` → `_diag.info(f"merged from: {', '.join(sources)}")` (the YAML body stays on `_console`/stdout).
- `runtime.py.jinja` `_pick_binding`: replace `raise SystemExit("error: no operation for '{cmd.key}' …")` with `_diag.fail(f"no operation for '{cmd.key}' matches the given arguments", code=2)`.

- [ ] **Step 4: Run the migrated-site test + update oracles**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py -k "config or history or pager" -q`
Expected: PASS. Update existing oracles that asserted the old plain message strings (the `error:`/`warning:` prefix and wording change):
- `test_config_bad_bool_env_ignored` — keep, or fold into the new test.
- history corrupt-lines / not-found tests — adjust to the `warning:`/`error:` wording.
- Confirmation oracles (`wrote {path}` / `history is empty` / `merged from`) that assert on `res.output` **stay as-is** — `res.output` is the combined stdout+stderr stream in click 8.4.1, so moving these to stderr does NOT break them. Do **not** switch them to `res.stdout`.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/*.jinja tests/test_cli_emitted.py
git commit -m "refactor(cli-gen): migrate all warning/error sites onto the diagnostics facade; confirmations -> info on stderr"
```

---

## Task 6: global `--quiet`/`-q`

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (inject option, pass to run)
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`run(..., quiet=False)` sets min level)
- Modify: `src/phantasos/generator/cli/render_cli.py` (add `"quiet"` to `_RESERVED`, line 25)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 0: Reserve the `quiet` param name**

In `src/phantasos/generator/cli/render_cli.py`, add `"quiet"` to `_RESERVED` (currently `{"output", "all_", "dry_run", "verbose", "self", "columns", "pager"}`) so an SDK body/query field named `quiet` is suffixed by `_py_name` and can't collide with the injected `--quiet` option (same reason `verbose`/`pager` are reserved).

- [ ] **Step 1: Write the failing test**

```python
def test_quiet_suppresses_warning_keeps_error(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    # --enabled bad value emits an error; with -q the error still shows.
    res = CliRunner().invoke(main.app, ["create", "widget", "--name", "w",
                                        "--priority", "1", "--enabled", "maybe", "-q"])
    assert res.exit_code == 2
    assert "error: --enabled" in res.stderr   # errors survive --quiet
```

(A warning-suppression assertion is added once a command path that emits a warning under
the fake client is identified; the error-survives check is the minimal guarantee.)

- [ ] **Step 2: Run it — verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_quiet_suppresses_warning_keeps_error -q`
Expected: FAIL (`-q` is an unknown option → exit 2 with a usage panel, not our error).

- [ ] **Step 3: Inject the option in commands.py.jinja**

In the common-options block (next to `verbose`), add:

```python
    quiet: bool = typer.Option(False, "--quiet", "-q", rich_help_panel="Common"),
```

and pass it in the `_rt.run(...)` call:

```python
        output=output, columns=columns, paginate_all=all_, dry_run=dry_run,
        verbose=verbose, quiet=quiet, pager=pager,
```

- [ ] **Step 4: Honor it in run()**

In `runtime.py.jinja`, change `run(...)`'s signature to accept `quiet: bool = False` and, at the very top of the body, add:

```python
    _diag.set_min_level(_diag.Level.ERROR if quiet else _diag.Level.INFO)
```

- [ ] **Step 5: Run the test — verify it passes**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py::test_quiet_suppresses_warning_keeps_error -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/commands.py.jinja \
        src/phantasos/generator/cli/templates/_generated/runtime.py.jinja \
        tests/test_cli_emitted.py
git commit -m "feat(cli-gen): global --quiet/-q suppresses info+warning (errors always shown)"
```

---

## Task 7: full gate + real-SDK + docs

**Files:**
- Modify: `docs/TODO.md` (note the file-logging + model-describe follow-ups, if a TODO list is maintained there)
- Test: whole suite

- [ ] **Step 1: Run the full CLI suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/test_cli_emitted.py tests/test_cli_emitted_real.py tests/test_cli_render.py tests/test_cli_command.py tests/test_cli_config.py -q`
Expected: PASS (all green; `test_generated_code_is_lint_clean` confirms the emitted `diagnostics.py` + edits are ruff-clean).

- [ ] **Step 2: Run lint on changed generator sources**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run ruff check src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py tests/test_cli_emitted_real.py tests/test_cli_render.py`
Expected: `All checks passed!`

- [ ] **Step 3: Run the whole test suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-repro uv run python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 4: Manual smoke against the real SDK (evidence)**

Run a one-off (mirrors `docs/research/2026-06-12-json-flag-error-ux.md` preview): build the real CLI to a temp dir and invoke `create application private … --urls "pb.example.com,pb2"`; confirm stderr shows the `✖ error:` + `expected:`/`example:`/`got:` block on a TTY and plain under `NO_COLOR=1`.

- [ ] **Step 5: Commit any doc/TODO updates**

```bash
git add docs/TODO.md
git commit -m "docs(cli-gen): note diagnostics follow-ups (file logging, model-describe flag)"
```

---

## Self-review checklist (run before handing off)

- [ ] **Spec coverage:** every row of the design's "Refactor map" has a Task 5 bullet; the facade (Task 1), render_error move (Task 2), Option A (Tasks 3-4), `--quiet` (Task 6) each map to a task.
- [ ] **No placeholders:** every code step shows real code; every run step shows the command + expected result.
- [ ] **Type consistency:** `Level`, `set_min_level`, `emit`, `error/warning/info/fail`, `render_error`, `_describe_json_field`, `InputError(message, expected, example, got, code)` are named identically across Tasks 1-6. `run(..., quiet=False)` and the `commands.py.jinja` `quiet=` kwarg match.
- [ ] **Stream discipline:** all new emissions go through `_diag.*` (stderr); only results stay on `_console`/stdout.
