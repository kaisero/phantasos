# CLI Structured Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-generate a config-driven, rotating JSON-Lines logfile into every CLI that captures Python warnings (the SDK enum pass-through) + CLI diagnostics off the terminal, plus `config set`/`config unset` to manage it. Implements GH #18→ wait #20.

**Architecture:** A new emitted `_generated/logging_setup.py` installs a `RotatingFileHandler` (JSONL, gzip-rotated) on the ROOT logger and calls `logging.captureWarnings(True)` so warnings route to the logfile (never stderr); `build_generated_app()` calls it once at startup; an `atexit` summary prints one terse stderr line when unknown enum values occurred. A new `logging` config section (level/file) rides the existing layered-config flow; `config set/unset` write `config.yml`.

**Tech Stack:** Python stdlib `logging` (`RotatingFileHandler`) + `gzip` — NO new third-party deps (keep the typer-slim footprint; the recent `click` regression is why — the `cli-smoke` gate must stay green). Jinja2 templates, Typer, pydantic, pytest.

---

## Context the implementer needs
- All paths are `src/phantasos/generator/cli/templates/_generated/*.jinja` unless noted. They are rendered per-product; emitted output is auto-formatted by `render_cli._format_generated` (ruff `--select I,UP` + `ruff format`), so emitted code only needs valid Python + correct imports.
- Gates (run all; the Stop hook runs `nox -s gate` = the first three): `UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run ruff check .` / `ruff format --check .` / `mypy` / `pytest -q`. Then the isolated gate: `NOX_ENVDIR=/tmp/phantasos-nox UV_PROJECT_ENVIRONMENT=/tmp/phantasos uv run nox -s cli-smoke --envdir /tmp/phantasos-nox`.
- Config model lives in `config.py.jinja`: sections `PagerConfig`/`OutputConfig`/`HistoryConfig` under `CliConfiguration`; `_ENV_MAP` maps env vars → dotted paths; `_BOOL_PATHS` marks bools; `effective_dict()` hand-lists every field (drives `config show`). The "Adding a CLI configuration option" flow in CLAUDE.md is the contract.
- `build_generated_app()` in `app.py.jinja` is regenerated on every `cli build` and is imported at CLI startup (`main.py`: `app = build_generated_app()`), so it's the right place to init logging.
- The SDK exposes unknown-enum tracking at `{sdk_package}._lenient.UNKNOWN_ENUM_VALUES` (a `dict[str, set]`), written by `src/phantasos/generator/sdk/patches.py` (`LENIENT_SOURCE`). The CLI reaches the sdk package via `runtime._ir().sdk_package`.
- `diagnostics.py.jinja` has `Level(IntEnum)` (INFO/WARNING/ERROR aligned to logging) + `emit()` → stderr (Rich). It documents a "future file sink" — we mirror its calls into the log.

## File Structure
- **Create** `_generated/logging_setup.py.jinja` — `init_logging()`, the JSONL formatter, the secure gzip-rotating handler, TRACE level, the `atexit` unknown-enum summary. One responsibility: stand up + own the log sink.
- **Modify** `config.py.jinja` — `LoggingConfig` section + `logging` field; `_ENV_MAP` rows; `effective_dict`; `log_file_path()` + `log_level_int()` helpers; a `level` field validator.
- **Modify** `default_config.yml.jinja` — commented `logging:` defaults + env-var reference rows.
- **Modify** `diagnostics.py.jinja` — mirror each `emit()` into a stdlib logger.
- **Modify** `app.py.jinja` — `build_generated_app()` calls `_logging_setup.init_logging()`.
- **Modify** `config_commands.py.jinja` — `config set` / `config unset`.
- **Modify** `tests/test_cli_emitted.py`, `tests/cli_isolated_smoke.py`, `CHANGELOG.md`.

---

## Task 1: `logging` config section + helpers

**Files:** Modify `config.py.jinja`, `default_config.yml.jinja`; Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing tests** (defaults, env override, level validation, default path)

```python
def test_logging_config_defaults_and_env(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    assert cfg.get().logging.level == "info"
    assert cfg.get().logging.file is None
    # default path is under logs/ next to config.yml
    assert cfg.log_file_path().name == "fakesdk_cli.jsonl"
    assert cfg.log_file_path().parent.name == "logs"
    # env override
    monkeypatch.setenv("FAKESDK_LOGGING_LEVEL", "debug")
    cfg.load_config.cache_clear()
    assert cfg.get().logging.level == "debug"
    assert cfg.log_level_int("warn") == 30 and cfg.log_level_int("trace") == 5

def test_logging_invalid_level_warns_and_falls_back(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"; (home / ".fakesdk_cli").mkdir(parents=True)
    (home / ".fakesdk_cli" / "config.yml").write_text(
        "configuration:\n  logging:\n    level: bogus\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    # bad level is rejected by _validate's bounded retry -> falls back to default
    assert cfg.get().logging.level == "info"
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** in `config.py.jinja`:

```python
from pydantic import field_validator  # add to imports

_LOG_LEVELS = {"trace": 5, "debug": 10, "info": 20,
               "warning": 30, "warn": 30, "error": 40, "critical": 50}

class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    level: str = "info"
    file: str | None = None  # None -> ~/.{distribution}/logs/{distribution}.jsonl

    @field_validator("level")
    @classmethod
    def _known_level(cls, v: str) -> str:
        if v.lower() not in _LOG_LEVELS:
            raise ValueError(
                f"unknown log level {v!r} (choose: trace, debug, info, "
                "warning, error, critical)"
            )
        return v.lower()
```
Add `logging: LoggingConfig = Field(default_factory=LoggingConfig)` to `CliConfiguration`. Add to `_ENV_MAP`:
`f"{_ENV_PREFIX}_LOGGING_LEVEL": ("configuration","logging","level")` and `f"{_ENV_PREFIX}_LOGGING_FILE": ("configuration","logging","file")`. Add to `effective_dict()` a `"logging": {"level": c.logging.level, "file": c.logging.file}` entry. Add module helpers:

```python
def log_level_int(name: str) -> int:
    return _LOG_LEVELS.get(name.lower(), 20)

def log_file_path() -> Path:
    f = get().logging.file
    if f:
        return Path(f).expanduser()
    return Path.home() / f".{_DISTRIBUTION}" / "logs" / f"{_DISTRIBUTION}.jsonl"
```
(The bad-level fallback works because `_validate`'s bounded retry deletes the offending key on `ValidationError` and re-validates → default `info`.)

- [ ] **Step 4: `default_config.yml.jinja`** — add a commented block + env-var rows:
```yaml
  # Logging: structured JSON-Lines log of warnings + diagnostics.
  # Per-invocation override: {{ env_prefix }}_LOGGING_LEVEL / _LOGGING_FILE.
  logging:
    # trace | debug | info | warning | error | critical
    level: info
    # null -> ~/.{{ distribution }}/logs/{{ distribution }}.jsonl
    file: null
```
Confirm `test_config_packaged_defaults_match_models` still passes (the new defaults mirror the model).

- [ ] **Step 5: Run → green. Commit.**

## Task 2: `logging_setup.py.jinja` — the sink

**Files:** Create `_generated/logging_setup.py.jinja`; register it in `render_cli.py` (render with the standard ctx, like the other `_generated/*.py`); Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing tests** (logfile created at default path, 0o600/0o700, warnings captured to file NOT stderr, JSONL format, terse summary)

```python
def test_logging_captures_warnings_to_file_not_stderr(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"; monkeypatch.setenv("HOME", str(home))
    ls = importlib.import_module("fakesdk_cli._generated.logging_setup")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    ls.init_logging()
    import warnings, json, stat, logging
    warnings.warn("DemoEnum: value 'x' is not defined in the OpenAPI spec")
    for h in logging.getLogger("py.warnings").handlers:  # flush; do NOT shutdown
        h.flush()
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    assert log.exists()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.parent.stat().st_mode) == 0o700
    line = json.loads(log.read_text().splitlines()[-1])
    assert line["level"] == "WARNING" and "not defined in the OpenAPI spec" in line["msg"]
    # NOT on stderr
    assert "not defined in the OpenAPI spec" not in capsys.readouterr().err
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `logging_setup.py.jinja`:

```python
"""Structured file logging for the {{ distribution }} CLI (injected by phantasos).

Installs a rotating JSON-Lines log sink on the ROOT logger and routes Python
warnings (e.g. the SDK's lenient-enum pass-through) into it instead of stderr.
A single terse stderr summary is emitted at exit if unknown enum values occurred.
"""
from __future__ import annotations

import atexit
import gzip
import importlib
import json
import logging
import shutil
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config as _config

TRACE = 5
_MAX_BYTES = 10 * 1024 * 1024
_BACKUPS = 3
_initialized = False


class _JsonlFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return json.dumps(
            {
                "ts": ts.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            },
            separators=(",", ":"),
        )


class _SecureRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that keeps the active log file private (0o600)."""

    def _open(self):  # type: ignore[override]
        stream = super()._open()
        try:
            Path(self.baseFilename).chmod(0o600)
        except OSError:
            pass
        return stream


def _gzip_rotator(source: str, dest: str) -> None:
    with open(source, "rb") as f_in, gzip.open(dest, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    Path(source).unlink(missing_ok=True)


def _gzip_namer(name: str) -> str:
    return name + ".gz"


def init_logging() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True
    logging.addLevelName(TRACE, "TRACE")
    path = _config.log_file_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.parent.chmod(0o700)
    except OSError:
        return  # never let logging setup break the CLI
    handler = _SecureRotatingFileHandler(
        str(path), maxBytes=_MAX_BYTES, backupCount=_BACKUPS,
        encoding="utf-8", delay=True,
    )
    handler.setFormatter(_JsonlFormatter())
    handler.rotator = _gzip_rotator
    handler.namer = _gzip_namer
    level = _config.log_level_int(_config.get().logging.level)
    # Attach the file sink to the `py.warnings` + `{{ package }}` loggers with
    # propagate=False — NEVER touch the root logger. This captures Python
    # warnings + our diagnostics into the file and keeps them off stderr (no
    # stdlib lastResort handler fires because py.warnings has a handler), while
    # leaving root / pytest's log-capture handler untouched. `handlers[:] = [..]`
    # (not addHandler) keeps it idempotent if init runs again in-process.
    for name in ("py.warnings", "{{ package }}"):
        lg = logging.getLogger(name)
        lg.handlers[:] = [handler]
        lg.setLevel(level)
        lg.propagate = False
    logging.captureWarnings(True)  # warnings -> 'py.warnings' logger -> file
    atexit.register(_emit_unknown_enum_summary, path)


def _emit_unknown_enum_summary(logfile: Path) -> None:
    try:
        from . import runtime as _rt
        mod = importlib.import_module(f"{_rt._ir().sdk_package}._lenient")
        unknown = getattr(mod, "UNKNOWN_ENUM_VALUES", {})
    except Exception:
        return
    n = sum(len(v) for v in unknown.values())
    if n:
        from . import diagnostics as _diag
        _diag.warning(f"{n} API value(s) not defined in the spec — see {logfile}")
```
Add to `render_cli.py`'s render list: `render("_generated/logging_setup.py.jinja", gen / "logging_setup.py")` (alongside the other `_generated` renders).

- [ ] **Step 4: Run → green.** Add a rotation test (construct a handler with a tiny `maxBytes`, write >1 line, assert a `.1.gz` appears and gunzips to the first line). **Commit.**

## Task 3: Wire init at startup + mirror diagnostics

**Files:** Modify `app.py.jinja`, `diagnostics.py.jinja`; Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing test** (a real command run leaves the logfile; diagnostics are mirrored)

```python
def test_app_inits_logging_and_mirrors_diag(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"; monkeypatch.setenv("HOME", str(home))
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    CliRunner().invoke(main.app, ["config", "show"])  # any command
    import logging
    for h in logging.getLogger("fakesdk_cli").handlers:  # flush; never shutdown()
        h.flush()
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    assert log.exists()  # init ran at app build
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement.** In `app.py.jinja`, at the top of `build_generated_app()` (before building Typers):
```python
    from . import logging_setup as _logging_setup
    _logging_setup.init_logging()
```
In `diagnostics.py.jinja`, mirror each emit into a logger (add near `emit()`):
```python
import logging
_log = logging.getLogger("{{ package }}.diagnostics")
_LEVEL_TO_LOGGING = {Level.INFO: logging.INFO, Level.WARNING: logging.WARNING,
                     Level.ERROR: logging.ERROR}
```
and at the end of `emit()` (after the console prints): `_log.log(_LEVEL_TO_LOGGING[level], message)`. (The console output is unchanged; this just also records to the log sink. The `_min_level` gate still controls the CONSOLE; the log records regardless so the file is complete.)

- [ ] **Step 4: Run → green.** Verify Python warnings no longer reach stderr through a full `CliRunner` command (assert the `UserWarning` text is absent from `.output`/`.stderr` while present in the logfile — monkeypatch the SDK to emit one, or call `warnings.warn` inside a patched command). **Commit.**

## Task 4: `config set` / `config unset`

**Files:** Modify `config_commands.py.jinja` (+ a config.yml writer); Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing tests** (alias + dotted set, unset, invalid → exit 2, show reflects)

```python
def test_config_set_unset(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"; monkeypatch.setenv("HOME", str(home))
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main"); r = CliRunner()
    assert r.invoke(main.app, ["config", "set", "loglevel", "debug"]).exit_code == 0
    data = yaml.safe_load((home / ".fakesdk_cli" / "config.yml").read_text())
    assert data["configuration"]["logging"]["level"] == "debug"
    assert r.invoke(main.app, ["config", "set", "output.format", "yaml"]).exit_code == 0
    # invalid value -> exit 2
    assert r.invoke(main.app, ["config", "set", "loglevel", "bogus"]).exit_code == 2
    # unknown key -> exit 2
    assert r.invoke(main.app, ["config", "set", "nope.key", "x"]).exit_code == 2
    # unset reverts
    assert r.invoke(main.app, ["config", "unset", "loglevel"]).exit_code == 0
    data = yaml.safe_load((home / ".fakesdk_cli" / "config.yml").read_text())
    assert "level" not in data.get("configuration", {}).get("logging", {})
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** in `config_commands.py.jinja`:

```python
_SET_ALIASES = {"loglevel": "logging.level", "logfile": "logging.file"}


def _resolve_key(key: str) -> tuple[str, ...]:
    dotted = _SET_ALIASES.get(key, key)
    return ("configuration", *dotted.split("."))


def _write_config(data: dict) -> None:
    path = _config.config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
    except OSError as exc:
        _diag.fail(f"cannot write {path}: {exc}", code=1)


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Set a config option in config.yml (e.g. `config set loglevel debug`)."""
    path = _resolve_key(key)
    raw = _config._raw_config_yml()  # see note
    node = raw
    for part in path[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            _diag.fail(f"cannot set '{key}': '{part}' is not a section", code=2)
    node[path[-1]] = _config.coerce_config_value(path, value)
    ok, err = _config.validate_config(raw)  # ConfigFile.model_validate, returns (bool, msg)
    if not ok:
        _diag.fail(f"invalid value for '{key}': {err}", code=2)
    _write_config(raw)
    _diag.info(f"set {'.'.join(path[1:])} = {node[path[-1]]!r}")


@config_app.command("unset")
def config_unset(key: str) -> None:
    """Remove a config option from config.yml (revert to the default)."""
    path = _resolve_key(key)
    raw = _config._raw_config_yml()
    node = raw
    for part in path[:-1]:
        node = node.get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            _diag.info(f"{key} not set"); return
    node.pop(path[-1], None)
    _write_config(raw)
    _diag.info(f"unset {'.'.join(path[1:])}")
```
Add the supporting helpers to `config.py.jinja`: `_raw_config_yml()` (safe-load `config_path()` → dict, `{}` if absent); `coerce_config_value(path, value)` (bool for `path in _BOOL_PATHS`; int for known int paths e.g. history.max_size_mb; else str — mirror the env coercion using `_TRUE`/`_FALSE`); `validate_config(raw)` (try `ConfigFile.model_validate(raw)`; return `(True, "")` or `(False, str(exc))` — this catches the bad-level via the field validator and unknown nested keys via the section models' `extra="allow"`... note unknown TOP-LEVEL section keys: validate by walking known fields; for an unknown key like `nope.key`, the `_resolve_key` produces `("configuration","nope","key")` → `CliConfiguration` has `extra="allow"` so it WON'T reject it. To make unknown keys exit 2, `validate_config` must reject extras: re-validate with a strict copy of the models OR check the path against the known schema. Simplest: a `_KNOWN_PATHS` set built from the models; `config set` rejects a key whose `path` isn't in `_KNOWN_PATHS`).

> **Decision for the implementer:** add `_known_config_paths() -> set[tuple]` derived from the pydantic models (walk `model_fields`), and have `config set`/`unset` reject keys not in it with exit 2 — this gives the "unknown key → exit 2" behaviour the test expects, independent of the `extra="allow"` leniency used for forward-compat file loading.

- [ ] **Step 4: Run → green. Commit.**

## Task 5: Smoke gate, CHANGELOG, docs

**Files:** Modify `tests/cli_isolated_smoke.py`, `CHANGELOG.md`, docs that enumerate config options (`docs/...` if any).

- [ ] **Step 1** — extend `cli_isolated_smoke.py`: after a command run, assert the logfile exists at `~/.fakesdk_cli/logs/fakesdk_cli.jsonl` with mode `0o600`; run `config set loglevel debug` then assert `config show` output contains `level: debug`; assert no raw `UserWarning`/`not defined in the OpenAPI spec` text on stderr of a normal run.
- [ ] **Step 2** — `CHANGELOG.md` `[Unreleased]`: add the logging feature + `config set`/`unset` entries.
- [ ] **Step 3** — update any config-option docs/reference.
- [ ] **Step 4** — full gate + `nox -s cli-smoke` green. **Commit.**

---

## Plan review corrections (2026-06-14)
- **M1 (applied above):** `init_logging` attaches the handler to the `py.warnings` + `{{ package }}` loggers with `propagate=False` — it must NEVER do `root.handlers[:] = [...]` (that evicts pytest's log-capture handler process-wide).
- **M2 (applied above):** tests must `flush()` the feature's specific handlers, NEVER call `logging.shutdown()` (it closes pytest's handlers for the rest of the session).
- **S1:** `init_logging` re-runs per test (the `emitted` fixture purges `fakesdk_cli.*`), so `atexit.register` is called once per test — harmless: the summary's `{sdk_package}._lenient` import fails for the `fakesdk` fixture (no `_lenient` module) → the `try/except` makes it a no-op; in a real CLI it runs once. Leave a comment noting this.
- **S2:** `config set`/`unset` rewrite `config.yml` via `yaml.safe_dump`, which strips the comments `config init` wrote. Acceptable for v1 — flag it in the CHANGELOG and the `config set` docstring (mention `config init --force` restores the commented template).
- **S3:** in `config set`/`config unset`, check the **resolved** path tuple (post-`_resolve_key`, after alias expansion) against `_known_config_paths()` — not the raw `key` string — so `loglevel`/`logfile` aliases validate correctly.

## Deferred / open
- Terse summary fires whenever unknown enum values occurred, regardless of `loglevel` (the per-value detail is in the log).
- JSONL fields beyond ts/level/logger/msg (command, request-id) — later.
- `history.jsonl` stays put (not moved under `logs/`).

## Self-review
- **Spec (#20) coverage:** logging section + env (T1); rotating gzip JSONL sink + captureWarnings + perms + summary (T2); startup init + diag mirror (T3); `config set/unset` + aliases + validation (T4); smoke/CHANGELOG (T5). ✓
- **No new deps:** stdlib `logging`+`gzip` only. ✓
- **Type consistency:** `log_file_path()`/`log_level_int()`/`_raw_config_yml()`/`coerce_config_value()`/`validate_config()`/`_known_config_paths()` defined in `config.py.jinja` (T1/T4) and used by `logging_setup`/`config_commands` (T2/T4); `init_logging()`/`TRACE` in `logging_setup` (T2) used by `app.py.jinja` (T3).
- **Gate-safety:** warnings routed ONLY to the file handler on root (no stderr handler), so `cli-smoke` sees a clean stderr; emitted code uses `Path.chmod` (PTH-clean).
