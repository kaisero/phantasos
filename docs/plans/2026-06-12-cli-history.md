# Generated-CLI Command History (WP1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every generated CLI records real API calls to a capped JSONL history file (`configuration.history.*`, on by default, bodies opt-in via `verbose`) and exposes them through `show cli history` (table) / `--entry <id>` (full JSON), with the `.env`→config harmony fix and the CLAUDE.md config-extension recipe.

**Architecture:** A new emitted `_generated/history.py` owns entry construction/append/read (best-effort, warn-and-continue); `runtime.run()` records after the SDK call (success and error paths; dry-run and meta commands never reach it); a new static `_generated/cli_commands.py` registers the reserved `cli` meta-object under the `show` verb. Config follows the established layered recipe (model + default YAML + `_ENV_MAP` + `effective_dict` + defaults-sync), and `load_config()` now loads `.env` first so every `{PREFIX}_*` option works from `.env`.

**Tech Stack:** Jinja templates (phantasos CLI generator), pydantic v2, Typer/Rich, JSONL, pytest (fake-SDK emitted tests + gated real-SDK tests).

**Spec:** `docs/specs/2026-06-12-cli-history-design.md` — READ FIRST; all decisions are user-confirmed.

---

## Process notes

- Work from `/home/ubuntu/git/phantasos`, branch `cli-generator`. NEVER `git checkout/switch/reset`.
- Tests: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run pytest …`.
- Behavioral tests go through the emitted package via the `emitted` fixture (tests/test_cli_emitted.py: renders the fakesdk CLI per test, purges `sys.modules["fakesdk_cli*"]`). Set HOME/env BEFORE `importlib.import_module`. Helpers available in that file: `_write_user_config(home, body)`, `_fake_client(recorder)` (mock ONLY at `facade.Client.from_env`), `_panel_titles(out)`.
- The fakesdk fixture has `fakesdk/exceptions.py` with `OpenApiException`/`ApiException` — the runtime's `_sdk_exc()` resolves it, so error-path tests can raise `fakesdk.exceptions.ApiException`.
- `command` is reconstructed from `sys.argv[1:]`; under pytest/CliRunner that's pytest's argv, so recording tests monkeypatch `sys.argv` (real CLI always has the real argv).
- `load_dotenv` mutates `os.environ` for the whole process — the `.env` test MUST clean up the variables it introduces (try/finally pop), or it pollutes later tests.
- Suite baseline: 271 passed, ruff + mypy clean.

## File map

| File | Change |
|---|---|
| `templates/_generated/config.py.jinja` | `HistoryConfig` model; `_ENV_MAP`/`_BOOL_PATHS` rows; `effective_dict`; `.env` load at top of `load_config()` |
| `templates/_generated/default_config.yml.jinja` | commented `history:` block + env-var reference |
| `templates/_generated/history.py.jinja` | NEW — append/read/id/cap (best-effort) |
| `templates/_generated/runtime.py.jinja` | record success/error entries around the SDK call |
| `templates/_generated/cli_commands.py.jinja` | NEW — `show cli history` (table/`--limit`/`--entry`) |
| `templates/_generated/app.py.jinja` | register `cli` meta-object under the `show` verb |
| `src/phantasos/generator/cli/render_cli.py` | emit the two new files; reserved-object guard (`cli`) |
| `CLAUDE.md` | NEW — harness-branch base + "Adding a CLI configuration option" recipe |
| `tests/test_cli_emitted.py`, `tests/test_cli_render.py`, `tests/test_cli_emitted_real.py` | behavioral + guard + gated tests |

(All template paths relative to `src/phantasos/generator/cli/`.)

---

### Task 1: Config foundation — `history:` section + `.env` harmony fix

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config.py.jinja`
- Modify: `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests** (append to tests/test_cli_emitted.py)

```python
def test_history_config_defaults_and_env(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    h = cfg.get().history
    assert h.enabled is True
    assert h.verbose is False
    assert h.file is None
    assert h.max_size_mb == 50
    assert cfg.effective_dict()["configuration"]["history"] == {
        "enabled": True, "verbose": False, "file": None, "max_size_mb": 50,
    }
    # env overrides (incl. int coercion through pydantic lax validation)
    monkeypatch.setenv("FAKESDK_HISTORY_ENABLED", "off")
    monkeypatch.setenv("FAKESDK_HISTORY_VERBOSE", "on")
    monkeypatch.setenv("FAKESDK_HISTORY_FILE", "/tmp/h.jsonl")
    monkeypatch.setenv("FAKESDK_HISTORY_MAX_SIZE_MB", "5")
    cfg.load_config.cache_clear()
    h = cfg.get().history
    assert h.enabled is False and h.verbose is True
    assert h.file == "/tmp/h.jsonl" and h.max_size_mb == 5


def test_dotenv_reaches_config_layer(emitted, monkeypatch, tmp_path):
    import os

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "FAKESDK_HISTORY_ENABLED=false\nFAKESDK_OUTPUT_FORMAT=yaml\n",
        encoding="utf-8",
    )
    try:
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        assert cfg.get().history.enabled is False   # .env -> config layer
        assert cfg.get().output.format == "yaml"
    finally:
        # load_dotenv writes into os.environ for the whole process — clean up
        os.environ.pop("FAKESDK_HISTORY_ENABLED", None)
        os.environ.pop("FAKESDK_OUTPUT_FORMAT", None)
```

- [ ] **Step 2: Run to verify red**

Run: `cd /home/ubuntu/git/phantasos && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "history_config or dotenv_reaches"`
Expected: FAIL — `AttributeError: ... has no attribute 'history'`.

- [ ] **Step 3: Implement in `config.py.jinja`**

(a) Add the model after `OutputConfig` and the field on `CliConfiguration`:

```python
class HistoryConfig(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    enabled: bool = True
    verbose: bool = False
    file: str | None = None
    max_size_mb: int = 50
```

```python
class CliConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    pager: PagerConfig = Field(default_factory=PagerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)
```

(b) Extend `_ENV_MAP` and `_BOOL_PATHS`:

```python
_ENV_MAP: dict[str, tuple[str, ...]] = {
    f"{_ENV_PREFIX}_PAGER_ENABLED": ("configuration", "pager", "enabled"),
    f"{_ENV_PREFIX}_PAGER_COMMAND": ("configuration", "pager", "command"),
    f"{_ENV_PREFIX}_OUTPUT_FORMAT": ("configuration", "output", "format"),
    f"{_ENV_PREFIX}_HISTORY_ENABLED": ("configuration", "history", "enabled"),
    f"{_ENV_PREFIX}_HISTORY_VERBOSE": ("configuration", "history", "verbose"),
    f"{_ENV_PREFIX}_HISTORY_FILE": ("configuration", "history", "file"),
    f"{_ENV_PREFIX}_HISTORY_MAX_SIZE_MB": ("configuration", "history", "max_size_mb"),
}
_BOOL_PATHS = {
    ("configuration", "pager", "enabled"),
    ("configuration", "history", "enabled"),
    ("configuration", "history", "verbose"),
}
```

(c) `.env` harmony fix — `load_config()` begins with (FIRST lines of the function body, before the packaged-defaults read; keep the existing docstring):

```python
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True))  # .env -> os.environ (config + auth)
    except ModuleNotFoundError:
        pass
```

(`_client()`'s own load_dotenv call stays — idempotent, and it covers exotic flows that bypass config.)

(d) `effective_dict()` gains the section:

```python
def effective_dict() -> dict[str, Any]:
    """The effective config as a clean dict (known keys only — extras excluded)."""
    c = get()
    return {
        "configuration": {
            "pager": {"enabled": c.pager.enabled, "command": c.pager.command},
            "output": {"format": c.output.format},
            "history": {
                "enabled": c.history.enabled,
                "verbose": c.history.verbose,
                "file": c.history.file,
                "max_size_mb": c.history.max_size_mb,
            },
        }
    }
```

- [ ] **Step 4: Extend `default_config.yml.jinja`**

Update the env-var reference comment block to include the four new variables, and add the section after `output:` (inside the `configuration:` mapping):

```yaml
#   {{ env_prefix }}_HISTORY_ENABLED      -> configuration.history.enabled
#   {{ env_prefix }}_HISTORY_VERBOSE      -> configuration.history.verbose
#   {{ env_prefix }}_HISTORY_FILE         -> configuration.history.file
#   {{ env_prefix }}_HISTORY_MAX_SIZE_MB  -> configuration.history.max_size_mb
```

```yaml
  # Command history: real API calls are appended to a JSON-Lines file
  # (one JSON object per line). View with `{{ distribution }} show cli history`.
  history:
    enabled: true
    # verbose: also record request and response BODIES in each entry.
    # WARNING: bodies may contain sensitive tenant data — the history file
    # is plain text in your home directory.
    verbose: false
    # null -> ~/.{{ distribution }}/history.jsonl
    file: null
    # When the file reaches this size the CLI warns and stops recording
    # (no automatic trimming). Delete the file to start fresh.
    max_size_mb: 50
```

- [ ] **Step 5: Run green + defaults-sync + full file**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q`
Expected: ALL pass — including the existing `test_config_packaged_defaults_match_models` (it auto-enforces YAML ≡ model defaults for the new section; if it fails, the YAML and model disagree — fix the mismatch, never the test).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja \
        src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja \
        tests/test_cli_emitted.py
git commit -m "feat(cli-gen): history config section + .env reaches the config layer"
```

---

### Task 2: The history module — append / read / id / cap

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/history.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (emission list)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

```python
def _hist(monkeypatch, tmp_path):
    """Import the emitted history module against an isolated HOME."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return importlib.import_module("fakesdk_cli._generated.history")


def test_history_record_appends_with_incrementing_ids(emitted, monkeypatch, tmp_path):
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t1", "command": "show widget", "status": "success"})
    hist.record({"ts": "t2", "command": "create widget", "status": "error"})
    entries, corrupt = hist.read_entries(0)
    assert corrupt == 0
    assert [e["id"] for e in entries] == [1, 2]
    assert entries[0]["command"] == "show widget"
    path = hist.history_path()
    assert path.name == "history.jsonl" and path.parent.name == ".fakesdk_cli"


def test_history_disabled_writes_nothing(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    enabled: false\n")
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t", "command": "x", "status": "success"})
    assert not hist.history_path().exists()


def test_history_cap_warns_and_skips(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    max_size_mb: 0\n")
    hist = _hist(monkeypatch, tmp_path)
    p = hist.history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"id": 1, "command": "old", "status": "success"}\n', encoding="utf-8")
    hist.record({"ts": "t", "command": "new", "status": "success"})
    err = capsys.readouterr().err
    assert "not recorded" in err and str(p) in err
    assert "new" not in p.read_text(encoding="utf-8")  # nothing appended


def test_history_read_skips_corrupt_lines_and_limits(emitted, monkeypatch, tmp_path):
    hist = _hist(monkeypatch, tmp_path)
    p = hist.history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"id": 1, "command": "a", "status": "success"}\n'
        "NOT JSON AT ALL\n"
        '{"id": 2, "command": "b", "status": "success"}\n'
        '{"id": 3, "command": "c", "status": "error"}\n',
        encoding="utf-8",
    )
    entries, corrupt = hist.read_entries(0)
    assert corrupt == 1 and [e["id"] for e in entries] == [1, 2, 3]
    last_two, _ = hist.read_entries(2)
    assert [e["id"] for e in last_two] == [2, 3]
    assert hist.read_entry(2)["command"] == "b"
    assert hist.read_entry(99) is None
    # id assignment continues past a corrupt trailing line
    p.write_text(p.read_text(encoding="utf-8") + "garbage\n", encoding="utf-8")
    hist.record({"ts": "t", "command": "d", "status": "success"})
    assert hist.read_entry(4)["command"] == "d"


def test_history_write_failure_warns_and_continues(emitted, monkeypatch, tmp_path, capsys):
    # Scoped failure injection: a read-only parent dir (NOT a global Path.mkdir
    # patch — hist.Path IS pathlib.Path; patching the class mutates the world).
    import os as _os

    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    if _os.access(locked, _os.W_OK):  # running as root: permission bits ineffective
        pytest.skip("cannot make dir read-only (running as privileged user)")
    home = tmp_path / "home"
    _write_user_config(
        home, f"configuration:\n  history:\n    file: {locked / 'sub' / 'h.jsonl'}\n"
    )
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t", "command": "x", "status": "success"})  # must not raise
    assert "could not write history" in capsys.readouterr().err
```

- [ ] **Step 2: Run to verify red**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "history_record or history_disabled or history_cap or history_read or history_write"`
Expected: FAIL — `ModuleNotFoundError: fakesdk_cli._generated.history`.

- [ ] **Step 3: Create `history.py.jinja`**

```python
"""Command history: JSONL append + read. Best-effort — never breaks a command."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import config as _config


def history_path() -> Path:
    cfg = _config.get().history
    if cfg.file:
        return Path(cfg.file).expanduser()
    return Path.home() / ".{{ distribution }}" / "history.jsonl"


def _last_id(path: Path) -> int:
    """id of the last parseable entry (tail scan; 0 if none)."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - 65536))
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return 0
    for line in reversed(tail.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("id"), int):
            return obj["id"]
    return 0


def record(entry: dict[str, Any]) -> None:
    """Append `entry` (id auto-assigned). Warns on any problem, never raises."""
    cfg = _config.get().history
    if not cfg.enabled:
        return
    path = history_path()
    try:
        if path.exists() and path.stat().st_size >= cfg.max_size_mb * 1024 * 1024:
            print(
                f"warning: history file full ({cfg.max_size_mb} MB cap) — command "
                f"not recorded; delete {path} or raise "
                "configuration.history.max_size_mb",
                file=sys.stderr,
            )
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        numbered = {"id": _last_id(path) + 1, **entry}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(numbered, default=str) + "\n")
    except OSError as exc:
        print(f"warning: could not write history: {exc}", file=sys.stderr)


def read_entries(limit: int = 0) -> tuple[list[dict[str, Any]], int]:
    """(entries oldest->newest, corrupt_line_count). limit=0 -> all, else last N."""
    path = history_path()
    if not path.exists():
        return [], 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"warning: could not read history: {exc}", file=sys.stderr)
        return [], 0
    entries: list[dict[str, Any]] = []
    corrupt = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            corrupt += 1
            continue
        if isinstance(obj, dict):
            entries.append(obj)
        else:
            corrupt += 1
    if limit > 0:
        entries = entries[-limit:]
    return entries, corrupt


def read_entry(entry_id: int) -> dict[str, Any] | None:
    """First entry with the given id (concurrent-append races keep first match)."""
    entries, _ = read_entries(0)
    for e in entries:
        if e.get("id") == entry_id:
            return e
    return None
```

- [ ] **Step 4: Emit it.** In `render_cli.py`, after the `config_commands.py` render line:

```python
    render("_generated/history.py.jinja", gen / "history.py")
```

- [ ] **Step 5: Run green** (same -k selection, then the whole file), **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/history.py.jinja \
        src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): emitted history module (JSONL append/read, cap warn-skip)"
```

---

### Task 3: Runtime recording — success/error entries around the SDK call

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

```python
def _run_show_widget(rt, **over):
    kw = dict(path={"id": "w1"}, body={}, query={}, output="json",
              paginate_all=False, dry_run=False, verbose=False)
    kw.update(over)
    rt.run("show:widget", **kw)


def test_runtime_records_success_and_error(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "show", "widget", "--id", "w1"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    _run_show_widget(rt)

    import fakesdk.exceptions as fx

    def _boom(**kw):
        exc = fx.ApiException("nope")
        exc.status = 404
        exc.body = '{"message": "widget not found"}'
        raise exc

    class _Failing:
        widgets = type("W", (), {"get_widget_by_id": staticmethod(_boom)})()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Failing()))
    with pytest.raises(SystemExit):
        _run_show_widget(rt)

    entries, _ = hist.read_entries(0)
    assert len(entries) == 2
    ok, bad = entries
    assert ok["id"] == 1 and ok["status"] == "success"
    assert ok["command"] == "show widget --id w1"
    assert ok["sdk_method"] == "widgets.get_widget_by_id"
    assert "http_status" not in ok and isinstance(ok["duration_ms"], int)
    assert "request_body" not in ok  # verbose off by default
    assert bad["status"] == "error" and bad["http_status"] == 404
    assert "not found" in bad["error"]


def test_runtime_dry_run_leaves_no_trace(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    _run_show_widget(rt, dry_run=True)
    assert not hist.history_path().exists()


def test_meta_commands_leave_no_trace(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    assert CliRunner().invoke(main.app, ["config", "show"]).exit_code == 0
    assert not hist.history_path().exists()


def test_runtime_verbose_records_bodies(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    verbose: true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "create", "widget", "--name", "x"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run("create:widget", path={}, body={"name": "x", "priority": 1}, query={},
           output="json", paginate_all=False, dry_run=False, verbose=False)
    (entry,), _ = hist.read_entries(0)
    assert entry["request_body"]["name"] == "x"
    assert entry["response_body"]["id"] == "new"
```

- [ ] **Step 2: Run to verify red**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "runtime_records or dry_run_leaves or meta_commands_leave or verbose_records"`
Expected: FAIL — no entries written (history module exists but runtime never calls it). NOTE: `test_meta_commands_leave_no_trace` may pass already (meta never hits runtime) — it is the regression lock.

- [ ] **Step 3: Implement in `runtime.py.jinja`**

(a) Imports: add `shlex`, `time`, `datetime` and the history module:

```python
import shlex
import time
from datetime import datetime, timezone
```
```python
from . import history as _history
```

(b) Add a module-level helper (near `_dry_run`):

```python
def _error_headline_for(exc: BaseException) -> str:
    """Same best-effort headline render_error shows: parsed-body first (via
    _output._error_headline), then str(exc), then the exception type name.
    (python-pro review: deriving from str(exc) alone violates the spec and
    misses the actionable server message.)"""
    body = getattr(exc, "body", None)
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    if isinstance(body, str) and body.strip():
        try:
            headline = _output._error_headline(json.loads(body))
        except ValueError:
            headline = None
        if headline:
            return headline[:300]
    text = str(exc).strip()
    return text.splitlines()[0][:300] if text else type(exc).__name__


def _history_entry(cmd: Command, binding: MethodBinding, status: str,
                   *, duration_ms: int | None = None,
                   exc: BaseException | None = None,
                   request_body: Any = None,
                   response: Any = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": shlex.join(sys.argv[1:]) if len(sys.argv) > 1 else cmd.key,
        "sdk_method": f"{cmd.sdk_resource}.{binding.sdk_method}",
        "status": status,
    }
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms
    if exc is not None:
        http_status = getattr(exc, "status", None)
        if http_status is not None:
            entry["http_status"] = http_status
        entry["error"] = _error_headline_for(exc)
    if _config_verbose():
        if request_body is not None:
            entry["request_body"] = _output._to_data(request_body)
        if response is not None:
            entry["response_body"] = _output._to_data(response)
    return entry


def _config_verbose() -> bool:
    from . import config as _config

    return _config.get().history.verbose
```

Also `import sys` if not already imported in the template (check — add if missing).

(c) In `run()`, around the SDK call (current code: `client = _client()` … `result = method(**kwargs)`), wrap with timing and record on both paths. The success path becomes:

```python
        client = _client()
        api = getattr(client, cmd.sdk_resource)
        method = getattr(api, binding.sdk_method)
        started = time.monotonic()
        if binding.sub_verb == "list" and paginate_all:
            pg = getattr(client, "paginate", None)
            result = list(pg(method, **kwargs)) if pg else method(**kwargs)
        else:
            result = method(**kwargs)
        duration_ms = int((time.monotonic() - started) * 1000)
        if hooks and (post := getattr(hooks, "after_call", None)) and callable(post):
            result = post(binding.sdk_method, result, cmd) or result
        _history.record(_history_entry(
            cmd, binding, "success", duration_ms=duration_ms,
            request_body=kwargs.get(binding.body_param) if binding.body_param else None,
            response=result,
        ))
        with _output.maybe_paged(pager):
            ...render unchanged...
```

and the except branch gains, BEFORE `render_error`:

```python
    except (_sdk_exc(), ValidationError) as exc:
        _history.record(_history_entry(cmd, binding, "error", exc=exc))
        if verbose:
            raise
        _output.render_error(exc)
        raise SystemExit(1) from exc
```

NOTE: `binding` is assigned before the `try:` block in the current template — verify, because the except handler now references it (it is: `_pick_binding` runs before `try`). The dry-run path returns before any recording — verify the `if dry_run:` return stays ABOVE the client call. `_history_entry`'s error path runs for failures DURING body build too (no API call made) — accepted by the spec's "errors reaching the except branch" reading; the entry simply has no `duration_ms`.

- [ ] **Step 4: Run green** (the -k selection, then the whole file). **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): runtime records history entries for real API calls"
```

---

### Task 4: `show cli history` + reserved-object guard

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja`
- Modify: `src/phantasos/generator/cli/templates/_generated/app.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (emission + guard)
- Test: `tests/test_cli_emitted.py`, `tests/test_cli_render.py`

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli_emitted.py`:

```python
def test_show_cli_history_table_limit_entry(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    hist = importlib.import_module("fakesdk_cli._generated.history")
    for i in range(25):
        hist.record({"ts": f"2026-06-12T0{i % 10}:00:00+00:00",
                     "command": f"show widget --id w{i}", "status": "success"})
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    res = r.invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "w24" in res.output           # newest included
    assert "w4" not in res.output        # default --limit 20 cuts the oldest 5
    assert "w5" in res.output

    res = r.invoke(main.app, ["show", "cli", "history", "--limit", "0"])
    assert "w0" in res.output            # everything

    res = r.invoke(main.app, ["show", "cli", "history", "--entry", "3"])
    assert res.exit_code == 0
    assert '"id"' in res.output and "w2" in res.output  # full JSON of entry 3

    res = r.invoke(main.app, ["show", "cli", "history", "--entry", "999"])
    assert res.exit_code == 1


def test_show_cli_history_empty_state(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "empty" in res.output
```

In `tests/test_cli_render.py` (imports of `CliIR`/`render_cli` exist; follow the file's IR-construction pattern — there are existing tests building a minimal `CliIR` with `Command(...)`; copy one and set `object="cli"`):

```python
def test_render_rejects_reserved_cli_object(tmp_path):
    from phantasos.generator.cli.ir import CliIR, Command, MethodBinding

    ir = CliIR(commands=[Command(
        verb="show", object="cli", key="show:cli", sdk_resource="clis",
        bindings=[MethodBinding(sdk_method="list_clis", sub_verb="list")],
    )])
    with pytest.raises(ValueError, match="reserved"):
        render_cli(ir, package="x_cli", out_dir=tmp_path)
```

(python-pro verified this minimal construction triggers the guard; if `CliIR`/`Command`
require additional mandatory fields at implementation time, satisfy the constructor —
never weaken the `match="reserved"` assertion.)

- [ ] **Step 2: Run to verify red** (`No such command 'cli'`; guard test fails with DID NOT RAISE).

- [ ] **Step 3: Create `cli_commands.py.jinja`**

```python
"""`show cli` meta-object: CLI introspection (history; future: status, changelog)."""

from __future__ import annotations

import typer
from rich.table import Table

from . import history as _history
from . import output as _output

cli_show_app = typer.Typer(no_args_is_help=True, help="CLI meta information.")


@cli_show_app.command("history")
def show_history(
    limit: int = typer.Option(20, "--limit", help="Entries to show (0 = all)."),
    entry: int | None = typer.Option(
        None, "--entry", help="Show ONE entry as full JSON (includes bodies if recorded)."
    ),
    pager: bool | None = typer.Option(
        None, "--pager/--no-pager",
        help="Page output taller than the terminal (default from config).",
        rich_help_panel="Common",
    ),
) -> None:
    """Show the command history (newest entries last)."""
    if entry is not None:
        e = _history.read_entry(entry)
        if e is None:
            typer.echo(f"error: no history entry with id {entry}", err=True)
            raise typer.Exit(1)
        _output._console.print_json(data=e)
        return
    entries, corrupt = _history.read_entries(limit)
    if corrupt:
        typer.echo(f"warning: skipped {corrupt} corrupt history line(s)", err=True)
    if not entries:
        typer.echo("history is empty")
        return
    table = Table("id", "date", "command", "status")
    for e in entries:
        # display timestamps to the minute (full ISO ts stays in the file/--entry)
        ts = str(e.get("ts", ""))[:16].replace("T", " ")
        table.add_row(
            str(e.get("id", "")), ts,
            str(e.get("command", "")), str(e.get("status", "")),
        )
    with _output.maybe_paged(pager):
        _output._console.print(table)
```

- [ ] **Step 4: Register + emit + guard**

(a) `app.py.jinja` — import after the config_commands import:

```python
from . import cli_commands as _cli_commands
```

and in `build_generated_app`, directly after the config-group registration line:

```python
    verb_apps["show"].add_typer(_cli_commands.cli_show_app, name="cli")
```

(b) `render_cli.py` — emit after the history.py render line:

```python
    render("_generated/cli_commands.py.jinja", gen / "cli_commands.py")
```

(c) `render_cli.py` — the guard, at the TOP of `render_cli()` (before any file writes):

```python
    reserved = sorted({c.object for c in ir.commands if c.object == "cli"})
    if reserved:
        raise ValueError(
            "object name 'cli' is reserved for CLI meta-commands "
            "(show cli history); rename the API object via a cli.yml override"
        )
```

- [ ] **Step 5: Run green + full gate**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src`
Expected: all pass / clean. (The gated real-SDK tests rebuild the CLI from the changed templates — `show --help` now lists `cli`; if an existing assertion counts `show` objects, update its expectation and report it.)

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja \
        src/phantasos/generator/cli/templates/_generated/app.py.jinja \
        src/phantasos/generator/cli/render_cli.py \
        tests/test_cli_emitted.py tests/test_cli_render.py
git commit -m "feat(cli-gen): show cli history (table/--entry) + reserved cli object guard"
```

---

### Task 5: CLAUDE.md + gated real test + rebuild + wrap

**Files:**
- Create: `CLAUDE.md` (repo root)
- Test: `tests/test_cli_emitted_real.py`
- Regenerates: `/home/ubuntu/git/prisma-browser-cli` (sibling — do NOT commit it)

- [ ] **Step 1: Create `CLAUDE.md`**

Base = the `worktree-harness-thin-slice` branch's file, verbatim (get it with
`git show worktree-harness-thin-slice:CLAUDE.md`), with the recipe section appended:

```markdown
## Adding a CLI configuration option (generated CLIs)

Every user-facing setting of a GENERATED CLI follows one layered flow — packaged
defaults <- `~/.{distribution}/config.yml` <- `.env` / shell env <- per-invocation
flags (where applicable). To add an option:

1. **Model field** — `src/phantasos/generator/cli/templates/_generated/config.py.jinja`:
   add the field to the right section model (frozen pydantic; a NEW section gets its
   own `XxxConfig` model wired into `CliConfiguration` via `Field(default_factory=…)`).
2. **Default + docs** — `default_config.yml.jinja`: add the commented entry. The YAML
   defaults MUST mirror the model defaults — the defaults-sync test
   (`test_config_packaged_defaults_match_models`) enforces it.
3. **Env var** — add an `_ENV_MAP` row named `{PREFIX}_{SECTION}_{KEY}` (the
   `configuration` wrapper is skipped). Booleans also join `_BOOL_PATHS`; ints ride
   pydantic lax coercion. `.env` works automatically: `load_config()` loads it first.
4. **`effective_dict()`** — extend it (drives `config show`).
5. **Tests** — behavioral, through the emitted package (`tests/test_cli_emitted.py`
   `emitted` fixture). Config is cached at command-module IMPORT: set HOME/env
   BEFORE `importlib.import_module`, and call `load_config.cache_clear()` after
   mutating the environment mid-test.
6. **Consumers** read via `_config.get().<section>.<key>` — never re-read files or
   env directly.
```

- [ ] **Step 2: Gated real-SDK test** (append to `tests/test_cli_emitted_real.py`)

```python
def test_real_history_records_and_shows(real_cli, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        sys, "argv", ["prisma-browser-cli", "show", "device-group", "--id", "DG1"]
    )
    mock = _patch_client(monkeypatch)
    mock.device_groups.get_device_group_by_id.return_value = {"id": "DG1", "name": "x"}
    main = importlib.import_module("prisma_browser_cli.main")
    r = CliRunner()
    assert r.invoke(main.app, ["show", "device-group", "--id", "DG1"]).exit_code == 0
    assert (tmp_path / ".prisma-browser-cli" / "history.jsonl").exists()
    res = r.invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "device-group" in res.output and "success" in res.output
```

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted_real.py -q` — PASS.

- [ ] **Step 3: Rebuild + manual verification**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
cd /home/ubuntu/git/prisma-browser-cli
export UV_PROJECT_ENVIRONMENT=/tmp/prisma-browser-cli-venv
uv sync -q --reinstall-package prisma-browser-cli
mkdir -p /tmp/hist-home
HOME=/tmp/hist-home uv run prisma-browser-cli show device-group --help | head -5  # cli object present under show? check `show --help` lists cli
HOME=/tmp/hist-home uv run prisma-browser-cli show cli history                   # "history is empty"
# live (uses repo .env): one real call, then history shows it
HOME=/tmp/hist-home uv run prisma-browser-cli show device-group 2>/dev/null | head -3
HOME=/tmp/hist-home uv run prisma-browser-cli show cli history
HOME=/tmp/hist-home uv run prisma-browser-cli show cli history --entry 1
HOME=/tmp/hist-home uv run prisma-browser-cli config show   # history section visible
rm -rf /tmp/hist-home
```

Also run the emitted suite in the project: `HOME=/tmp/hist-home2 uv run pytest tests/ -q; rm -rf /tmp/hist-home2`.

- [ ] **Step 4: Full gate + docs + memory**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src
```

Update `docs/TODO.md`: mark "History File and Show command" DONE with a pointer to the
spec (note the --verbose supersession by table-default + `--entry`). Update the
`prisma-browser-cli-generator-design` memory entry (decisions, HEAD, the `.env` fix,
CLAUDE.md created, WP2 Logfile next). Commit:

```bash
git add CLAUDE.md tests/test_cli_emitted_real.py docs/TODO.md
git commit -m "feat(cli-gen): CLAUDE.md config recipe + gated history e2e; TODO update"
```

Handoff: sibling regenerated uncommitted; the `.env`-in-CWD note (find_dotenv anchors
to the user's working directory, unchanged from the auth flow).

---

## Self-review (done at planning time)

- **Spec coverage:** config schema/env/.env fix → T1; JSONL module incl. cap/corruption/id → T2; recording scope + entry schema + verbose bodies → T3; read side + reserved guard → T4; CLAUDE.md + real validation + TODO/memory → T5. Out-of-scope items have no tasks (correct).
- **Type consistency:** `record(entry: dict)`, `read_entries(limit) -> (list, int)`, `read_entry(id) -> dict|None` used identically in T2 (def), T3 (record calls), T4 (read calls). `_history_entry` signature matches both call sites.
- **Known judgment points for the implementer:** the runtime template must already import `sys` (verify; add if missing); `binding` is bound before `try:` (verified in plan); `test_meta_commands_leave_no_trace` is a regression lock that may pass immediately.

---

### Task 6 (2026-06-12 follow-up, user-requested): http_method/http_uri by default

Per the spec addendum: wrap `api_client.call_api` around the real SDK call in
`runtime.py.jinja` (capture first `(method, url)` into a dict defined BEFORE the outer
try so the except branch sees it; restore in finally); `_history_entry` gains an
`http: dict[str, str] | None` param merged into the entry after `sdk_method`. Tests:
capture on success (fake api whose method calls its own `api_client.call_api`),
capture on error (call_api raises ApiException after capture), fields absent for
plain fakes (no api_client). Then full gate + real rebuild + live verification.
