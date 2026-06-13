# Generated-CLI User Config + Opt-in Pager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every generated CLI gains a layered user config file (packaged defaults ← `~/.{distribution}/config.yml` ← env ← flags) whose first consumers are an opt-in auto-threshold pager and the default `--output` format, plus `config init` / `config show` meta-commands.

**Architecture:** Typed pydantic models in the emitted `_generated/config.py` (Approach A per the spec); config loads cached at **command-module import** (Typer freezes option defaults then); the pager is a Rich `Console.pager()` with a custom `_AutoPager` that pages only when content is taller than the terminal and stdout is a TTY.

**Tech Stack:** Jinja templates (phantasos CLI generator), pydantic v2, Typer, Rich, PyYAML, pytest (fake-SDK emitted-CLI tests + gated real-SDK tests).

**Spec:** `docs/superpowers/specs/2026-06-11-cli-user-config-pager-design.md` — READ IT FIRST. All decisions there are user-approved and python-pro-verified; do not re-litigate.

---

## Process notes (read before Task 1)

- Work from `/home/ubuntu/git/phantasos`, branch `cli-generator`. NEVER `git checkout/switch/reset`.
- Test env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run pytest …` (repo `.venv` is on sshfs, can't hold symlinks).
- Testing methodology (established): behavioral tests against the EMITTED package via the `emitted` fixture (fake SDK) — never assert on raw template text unless structural; emitted code is post-formatted by ruff, so source assertions must be formatting-robust. Real-SDK e2e mocks ONLY at the `facade.Client.from_env` boundary, never `rt._client`. Gated tests skip when the sibling SDK is absent.
- **Config load timing (the python-pro blocker — internalize this):** `typer.Option(...)` defaults are frozen when the command module is imported, and `_generated/app.py` imports all command modules at its own import. Config therefore loads (cached `functools.cache`) at first command-module import. Tests MUST set `HOME`/env vars BEFORE importing any `fakesdk_cli` module; the `emitted` fixture purges `sys.modules["fakesdk_cli*"]` per test, which also resets the cache and the warn-once flag.
- The fakesdk fixture renders with `package="fakesdk_cli"`, NO distribution → distribution falls back to the package name → the homedir config dir in fake-SDK tests is `~/.fakesdk_cli/`. The real CLI uses `~/.prisma-browser-cli/`.
- Suite baseline: 248 passed, ruff + mypy clean.

## File map

| File | Change |
|---|---|
| `src/phantasos/generator/cli/templates/_generated/config.py.jinja` | REWRITE — models, load pipeline, warnings, accessors |
| `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja` | NEW — commented shipped defaults |
| `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja` | NEW — `config init`/`config show` |
| `src/phantasos/generator/cli/templates/_generated/output.py.jinja` | EXTEND — `_AutoPager`, `maybe_paged`, yaml `end=""` |
| `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` | EXTEND — `pager` param, engagement |
| `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` | EXTEND — `--output` default from config, `--pager/--no-pager` |
| `src/phantasos/generator/cli/templates/_generated/app.py.jinja` | EXTEND — register `config` group, `rich_help_panel="CLI"` |
| `src/phantasos/generator/cli/render_cli.py` | emit new files; `_RESERVED` += `"pager"` |
| `src/phantasos/generator/cli/scaffold_context.py` | `_CLI_DEPS` += `pydantic>=2.11` |
| `src/phantasos/generator/cli/cli_overrides/tests/test_config.py.jinja` | NEW — emitted CLI's own config tests |
| `tests/test_cli_emitted.py` | REPLACE `test_config_precedence`; add config/pager/flag tests |
| `tests/test_cli_emitted_real.py` | add gated `config init/show` test |

---

### Task 1: Config core — models, load pipeline, packaged defaults

**Files:**
- Rewrite: `src/phantasos/generator/cli/templates/_generated/config.py.jinja`
- Create: `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (~line 304, emission list)
- Test: `tests/test_cli_emitted.py` (replace `test_config_precedence`, lines 65-73)

- [ ] **Step 1: Replace `test_config_precedence` with the new behavioral tests**

Delete `test_config_precedence` (tests/test_cli_emitted.py:65-73) and add (note: `importlib`, `sys`, `Path`, `pytest` already imported at the top of the file):

```python
def _write_user_config(home, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def test_config_defaults_when_no_user_file(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    c = cfg.get()
    assert c.pager.enabled is False
    assert c.pager.command is None
    assert c.output.format == "json"
    assert cfg.load_config()[1] == ()  # no warnings


def test_config_packaged_defaults_match_models(emitted):
    import yaml as _yaml
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    data = _yaml.safe_load(cfg.packaged_default_text())
    assert cfg.ConfigFile.model_validate(data) == cfg.ConfigFile()


def test_config_homedir_override_and_env_precedence(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    _write_user_config(
        home,
        "configuration:\n  output:\n    format: table\n  pager:\n    enabled: true\n",
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "table"
    assert cfg.get().pager.enabled is True
    # env beats file (clear the cache after mutating the environment)
    monkeypatch.setenv("FAKESDK_OUTPUT_FORMAT", "yaml")
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "off")
    cfg.load_config.cache_clear()
    assert cfg.get().output.format == "yaml"
    assert cfg.get().pager.enabled is False
    assert "environment variables" in cfg.load_config()[2]


def test_config_unknown_key_warns_once(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pagre:\n    enabled: true\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.get()
    cfg.get()  # second call must not re-warn
    err = capsys.readouterr().err
    assert err.count("unknown config key 'configuration.pagre'") == 1


def test_config_wrong_type_falls_back(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pager:\n    enabled: maybe\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False  # default applied
    err = capsys.readouterr().err
    assert "configuration.pager.enabled" in err and "default" in err


def test_config_malformed_yaml_ignores_file(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, ":: this is not yaml ::\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "json"  # defaults survive
    assert "invalid YAML" in capsys.readouterr().err


def test_config_bad_bool_env_ignored(emitted, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "banana")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False
    assert "not a boolean" in capsys.readouterr().err
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd /home/ubuntu/git/phantasos && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k config`
Expected: FAIL — `AttributeError: module 'fakesdk_cli._generated.config' has no attribute 'get'` (old `resolve()`-style module still emitted).

- [ ] **Step 3: Write `default_config.yml.jinja`**

Create `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja`:

```yaml
# {{ distribution }} configuration file.
#
# Written by `{{ distribution }} config init` from the packaged defaults.
# Location: ~/.{{ distribution }}/config.yml
# Precedence: command-line flags > environment variables > this file >
# packaged defaults.
#
# Environment variable reference:
#   {{ env_prefix }}_PAGER_ENABLED  -> configuration.pager.enabled
#   {{ env_prefix }}_PAGER_COMMAND  -> configuration.pager.command
#   {{ env_prefix }}_OUTPUT_FORMAT  -> configuration.output.format

configuration:
  # Pager for long output: when enabled, results taller than the terminal are
  # shown in a pager. Never engages when output is piped or redirected.
  # Per-invocation override: --pager / --no-pager.
  pager:
    enabled: false
    # Pager program. null -> $PAGER -> 'less -RFX'.
    command: null

  output:
    # Default output format for results: json | yaml | table.
    # Per-invocation override: --output.
    format: json
```

- [ ] **Step 4: Rewrite `config.py.jinja`**

Replace the entire content of `src/phantasos/generator/cli/templates/_generated/config.py.jinja`:

```python
"""User configuration: packaged defaults <- ~/.{{ distribution }}/config.yml <- env.

Loaded once per process (cached) at first command-module import — Typer option
defaults are frozen at import time, so the effective config must resolve before
they are evaluated. Problems never abort the CLI: unknown keys and bad values
warn on stderr and fall back (see the design spec).
"""

from __future__ import annotations

import functools
import os
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

_ENV_PREFIX = "{{ env_prefix }}"
_DISTRIBUTION = "{{ distribution }}"


class PagerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    command: str | None = None


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    format: str = "json"


class CliConfiguration(BaseModel):
    model_config = ConfigDict(extra="allow")
    pager: PagerConfig = Field(default_factory=PagerConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


class ConfigFile(BaseModel):
    model_config = ConfigDict(extra="allow")
    configuration: CliConfiguration = Field(default_factory=CliConfiguration)


# env var -> path into the merged dict (the `configuration` level is explicit)
_ENV_MAP: dict[str, tuple[str, ...]] = {
    f"{_ENV_PREFIX}_PAGER_ENABLED": ("configuration", "pager", "enabled"),
    f"{_ENV_PREFIX}_PAGER_COMMAND": ("configuration", "pager", "command"),
    f"{_ENV_PREFIX}_OUTPUT_FORMAT": ("configuration", "output", "format"),
}
_BOOL_PATHS = {("configuration", "pager", "enabled")}
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def config_path() -> Path:
    return Path.home() / f".{_DISTRIBUTION}" / "config.yml"


def packaged_default_text() -> str:
    return files(__package__).joinpath("default_config.yml").read_text(
        encoding="utf-8"
    )


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = data
    for part in path[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[path[-1]] = value


def _del_path(data: dict[str, Any], path: tuple[str, ...]) -> None:
    # Dict paths only — sufficient for the whole v1 schema. Revisit when the
    # future `environments:` LIST lands (int locs shift on deletion).
    node: Any = data
    for part in path[:-1]:
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            return
    if isinstance(node, dict):
        node.pop(path[-1], None)


def _validate(merged: dict[str, Any], warnings: list[str]) -> ConfigFile:
    data = merged
    for _ in range(16):  # bounded: each pass removes the offending keys
        try:
            return ConfigFile.model_validate(data)
        except ValidationError as exc:
            for err in exc.errors():
                loc = tuple(str(p) for p in err["loc"])
                warnings.append(
                    f"config key {'.'.join(loc)}: {err['msg']} (using default)"
                )
                _del_path(data, loc)
    return ConfigFile()


def _collect_extras(
    model: BaseModel, prefix: tuple[str, ...], warnings: list[str]
) -> None:
    for key in getattr(model, "__pydantic_extra__", None) or {}:
        dotted = ".".join([*prefix, key])
        warnings.append(f"unknown config key '{dotted}' (ignored)")
    for name in type(model).model_fields:
        value = getattr(model, name, None)
        if isinstance(value, BaseModel):
            _collect_extras(value, (*prefix, name), warnings)


@functools.cache
def load_config() -> tuple[ConfigFile, tuple[str, ...], tuple[str, ...]]:
    """(config, warnings, sources). Cached; cache lives on this module, so test
    harnesses that purge ``sys.modules`` (the established fixture pattern) get a
    fresh load. Mutating env/HOME mid-process requires ``load_config.cache_clear()``.
    """
    warnings: list[str] = []
    sources = ["packaged defaults"]
    try:
        merged: dict[str, Any] = yaml.safe_load(packaged_default_text()) or {}
    except Exception:  # packaged file unreadable -> model defaults still apply
        merged = {}
    path = config_path()
    if path.exists():
        try:
            user = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            warnings.append(f"{path}: invalid YAML (file ignored): {exc}")
            user = None
        if isinstance(user, dict):
            merged = _deep_merge(merged, user)
            sources.append(str(path))
        elif user is not None:
            warnings.append(f"{path}: not a mapping (file ignored)")
    env_applied = False
    for var, dotted in _ENV_MAP.items():
        raw = os.environ.get(var)
        if raw is None:
            continue
        value: Any = raw
        if dotted in _BOOL_PATHS:
            low = raw.strip().lower()
            if low in _TRUE:
                value = True
            elif low in _FALSE:
                value = False
            else:
                warnings.append(f"{var}={raw!r}: not a boolean (ignored)")
                continue
        _set_path(merged, dotted, value)
        env_applied = True
    if env_applied:
        sources.append("environment variables")
    cfg = _validate(merged, warnings)
    _collect_extras(cfg, (), warnings)
    return cfg, tuple(warnings), tuple(sources)


_warned = False


def warn_once() -> None:
    """Print collected config warnings to stderr, once per process."""
    global _warned
    if _warned:
        return
    _warned = True
    for w in load_config()[1]:
        print(f"warning: {w}", file=sys.stderr)


def get() -> CliConfiguration:
    cfg, _warnings, _sources = load_config()
    warn_once()
    return cfg.configuration


def default_output() -> str:
    """Effective default for --output (evaluated at command-module import)."""
    return get().output.format


def effective_dict() -> dict[str, Any]:
    """The effective config as a clean dict (known keys only — extras excluded)."""
    c = get()
    return {
        "configuration": {
            "pager": {"enabled": c.pager.enabled, "command": c.pager.command},
            "output": {"format": c.output.format},
        }
    }
```

- [ ] **Step 5: Emit the new file in `render_cli.py`**

In `render_cli` (after the `render("_generated/config.py.jinja", ...)` line at ~304), add:

```python
    render("_generated/default_config.yml.jinja", gen / "default_config.yml")
```

- [ ] **Step 6: Run the new tests**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k config`
Expected: PASS (all 7 new config tests).

- [ ] **Step 7: Run the whole emitted suite + lint**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py tests/test_cli_render.py -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests`
Expected: PASS / clean. (Nothing imports `config.resolve` — the dead API had no consumers.)

- [ ] **Step 8: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja \
        src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja \
        src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): typed layered user config (packaged defaults <- homedir <- env)"
```

---

### Task 2: Pager machinery in `output.py` (+ yaml `end=""` fix)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/output.py.jinja`
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_emitted.py`:

```python
def test_yaml_output_has_no_trailing_blank_line(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode="python"):
            return {"a": 1}

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert text.endswith("a: 1\n")
    assert not text.endswith("\n\n")


def test_autopager_short_content_writes_direct(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "10")
    monkeypatch.setenv("COLUMNS", "80")
    pager = out._AutoPager("/definitely/not/a/pager")
    pager.show("one\ntwo\nthree\n")  # 3 lines < 10 -> no spawn attempt
    captured = capsys.readouterr()
    assert "one\ntwo\nthree\n" in captured.out
    assert captured.err == ""  # no missing-binary warning -> nothing was spawned


def test_autopager_tall_content_pipes_to_command(emitted, monkeypatch, tmp_path):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "10")
    monkeypatch.setenv("COLUMNS", "80")
    sink = tmp_path / "paged.txt"
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager(f"tee {sink}").show(content)
    assert sink.read_text(encoding="utf-8") == content


def test_autopager_missing_binary_falls_back(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager("/definitely/not/a/pager").show(content)
    captured = capsys.readouterr()
    assert captured.out.endswith("line49\n")  # content not lost
    assert "pager command not found" in captured.err


def test_pager_command_resolution(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("PAGER", raising=False)
    out = importlib.import_module("fakesdk_cli._generated.output")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert out.pager_command() == "less -RFX"  # built-in fallback
    monkeypatch.setenv("PAGER", "mypager")
    assert out.pager_command() == "mypager"  # $PAGER beats fallback
    _write_user_config(
        home, "configuration:\n  pager:\n    command: bat --paging=always\n"
    )
    cfg.load_config.cache_clear()
    assert out.pager_command() == "bat --paging=always"  # config beats $PAGER


def test_maybe_paged_skips_when_not_a_tty(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: False)
    with out.maybe_paged(True):
        out._console.print("hello")
    assert "hello" in capsys.readouterr().out  # rendered directly, no pager


def test_maybe_paged_uses_pager_when_tty(emitted, monkeypatch, tmp_path):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: True)
    sink = tmp_path / "paged.txt"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with out.maybe_paged(True):
        for i in range(50):
            out._console.print(f"row{i}")
    assert "row49" in sink.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "pager or yaml_output"`
Expected: FAIL — `AttributeError: ... has no attribute '_AutoPager'` (and the yaml test fails on `\n\n` only AFTER the refactor in this task — initially it passes with bare print; that's fine, it's the regression lock).

- [ ] **Step 3: Implement in `output.py.jinja`**

(a) Extend the imports block (top of file):

```python
import json
import os
import re
import shlex
import subprocess
import sys
from contextlib import contextmanager
from typing import Any

import jmespath
import yaml
from rich.console import Console
from rich.pager import Pager
from rich.table import Table

from . import config as _config
```

(b) In `render()`, change the yaml branch from `print(...)` to (the `end=""` is REQUIRED — `Console.out` appends a newline; `safe_dump` already ends with one):

```python
    if fmt == "yaml":
        _console.out(
            yaml.safe_dump(data, sort_keys=False, default_flow_style=False),
            highlight=False,
            end="",
        )
        return
```

(c) Append the pager section at the end of the file:

```python
# ---- pager -----------------------------------------------------------------


def _stdout_is_tty() -> bool:  # module-level for monkeypatching in tests
    return sys.stdout.isatty()


def pager_command() -> str:
    """configuration.pager.command > $PAGER > 'less -RFX'."""
    return _config.get().pager.command or os.environ.get("PAGER") or "less -RFX"


class _AutoPager(Pager):
    """Pages only when content is taller than the terminal; short content is
    written directly (no process spawned). Receives the fully rendered ANSI
    text from rich's pager context. The threshold counts logical lines — a
    deliberate approximation (see spec)."""

    def __init__(self, command: str) -> None:
        self._command = command

    def show(self, content: str) -> None:
        if content.count("\n") <= max(_console.size.height - 1, 1):
            sys.stdout.write(content)
            return
        argv = shlex.split(self._command)
        try:
            # run(input=...) absorbs the user quitting the pager early.
            subprocess.run(argv, input=content, text=True, check=False)
        except FileNotFoundError:
            print(f"warning: pager command not found: {argv[0]}", file=sys.stderr)
            sys.stdout.write(content)


@contextmanager
def maybe_paged(flag: bool | None):
    """Wrap rendering in the auto-threshold pager when it should engage.

    flag is the tri-state --pager/--no-pager value; None defers to config.
    Never engages when stdout is not a TTY (pipes/redirects keep working).
    """
    enabled = flag if flag is not None else _config.get().pager.enabled
    if not (enabled and _stdout_is_tty()):
        yield
        return
    with _console.pager(pager=_AutoPager(pager_command()), styles=True):
        yield
```

- [ ] **Step 4: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q`
Expected: PASS (all, including the pre-existing `test_output_formats` — the yaml change is byte-identical).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/output.py.jinja tests/test_cli_emitted.py
git commit -m "feat(cli-gen): auto-threshold Rich pager (_AutoPager + maybe_paged); yaml via console"
```

---

### Task 3: Flag wiring — `--output` default from config, `--pager/--no-pager`, runtime engagement

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` (lines 19, 30-40)
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (run() signature ~171, render call ~233)
- Modify: `src/phantasos/generator/cli/render_cli.py:25` (`_RESERVED`)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_emitted.py` (mocking ONLY at the facade boundary, per the methodology):

```python
def test_output_default_comes_from_config(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: yaml\n")
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0
    assert "id: w1" in res.output  # yaml rendering proves the config default applied

    # and --help shows the effective default
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "yaml" in res.output


def test_pager_flag_present_and_run_wires_it(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "--pager" in res.output and "--no-pager" in res.output

    out = importlib.import_module("fakesdk_cli._generated.output")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.extras.facade as facade

    calls: list = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    seen: list = []

    from contextlib import contextmanager

    @contextmanager
    def _spy(flag):
        seen.append(flag)
        yield

    monkeypatch.setattr(out, "maybe_paged", _spy)
    rt.run("show:widget", path={"id": "w1"}, body={}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False, pager=True)
    assert seen == [True]
```

- [ ] **Step 2: Run to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "output_default or pager_flag"`
Expected: FAIL — `--pager` absent from help; `run() got an unexpected keyword argument 'pager'`.

- [ ] **Step 3: Implement**

(a) `commands.py.jinja` — add the config import (after `from .. import runtime as _rt`):

```python
from .. import config as _cfg
```

Replace line 19 (`output: str = typer.Option("json", "--output"),`) with:

```python
    output: str = typer.Option(_cfg.default_output(), "--output"),
```

Add after the `verbose` option (line 30):

```python
    pager: bool | None = typer.Option(
        None,
        "--pager/--no-pager",
        help="Page output taller than the terminal (default from config).",
    ),
```

And pass it through in the `_rt.run(...)` call (line 40):

```python
        output=output, columns=columns, paginate_all=all_, dry_run=dry_run, verbose=verbose,
        pager=pager,
```

(b) `runtime.py.jinja` — extend the `run()` signature (~line 171):

```python
def run(key: str, *, path: dict[str, Any], body: dict[str, Any],
        query: dict[str, Any], output: str, paginate_all: bool,
        dry_run: bool, verbose: bool,
        columns: list[str] | None = None,
        pager: bool | None = None) -> None:
```

and wrap ONLY the render call (~line 233):

```python
        with _output.maybe_paged(pager):
            _output.render(
                result, fmt=output, columns=columns,
                default_columns=[(c.header, c.path) for c in cmd.columns],
                items_field=cmd.items_field,
            )
```

(`pager=None` default keeps every existing `rt.run(...)` test call working.)

(c) `render_cli.py:25` — reserve the name (a body/query field literally named `pager` must not collide):

```python
_RESERVED = {"output", "all_", "dry_run", "verbose", "self", "columns", "pager"}
```

- [ ] **Step 4: Run the suite**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py tests/test_cli_command.py tests/test_cli_render.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/commands.py.jinja \
        src/phantasos/generator/cli/templates/_generated/runtime.py.jinja \
        src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): --output default from config; --pager/--no-pager wired into runtime"
```

---

### Task 4: `config init` / `config show` + app registration with its own help panel

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja`
- Modify: `src/phantasos/generator/cli/templates/_generated/app.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (emission list)
- Test: `tests/test_cli_emitted.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_config_init_and_show_commands(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    res = r.invoke(main.app, ["config", "init"])
    assert res.exit_code == 0
    target = tmp_path / ".fakesdk_cli" / "config.yml"
    assert target.exists()
    assert "pager" in target.read_text(encoding="utf-8")  # commented defaults

    res = r.invoke(main.app, ["config", "init"])
    assert res.exit_code == 1  # refuses without --force

    res = r.invoke(main.app, ["config", "init", "--force"])
    assert res.exit_code == 0

    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "merged from" in res.output
    assert str(target) in res.output  # homedir file listed as a source
    assert "format: json" in res.output


def test_config_group_in_its_own_help_panel(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--help"])
    assert res.exit_code == 0
    assert "config" in res.output
    assert "CLI" in res.output  # the dedicated panel title renders
```

- [ ] **Step 2: Run to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q -k "config_init or config_group"`
Expected: FAIL — `No such command 'config'`.

- [ ] **Step 3: Create `config_commands.py.jinja`**

```python
"""`config` meta-commands: manage the {{ distribution }} user configuration file."""

from __future__ import annotations

import typer
import yaml

from . import config as _config

config_app = typer.Typer(
    no_args_is_help=True, help="Manage the CLI configuration file."
)


@config_app.command("init")
def config_init(
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing config file."
    ),
) -> None:
    """Write the commented default configuration to ~/.{{ distribution }}/config.yml."""
    path = _config.config_path()
    if path.exists() and not force:
        typer.echo(f"error: {path} exists (use --force to overwrite)", err=True)
        raise typer.Exit(1)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_config.packaged_default_text(), encoding="utf-8")
    except OSError as exc:
        typer.echo(f"error: cannot write {path}: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"wrote {path}")


@config_app.command("show")
def config_show() -> None:
    """Print the effective merged configuration and where it came from."""
    _cfg, _warnings, sources = _config.load_config()
    _config.warn_once()
    typer.echo("# merged from: " + ", ".join(sources))
    typer.echo(
        yaml.safe_dump(
            _config.effective_dict(), sort_keys=False, default_flow_style=False
        ),
        nl=False,
    )
```

- [ ] **Step 4: Register in `app.py.jinja` and emit**

In `app.py.jinja`, add the import (after the resource-module import loop, before `_DISTRIBUTION`):

```python
from . import config_commands as _config_commands
```

In `build_generated_app`, after the verb-apps loop (`for v, t in verb_apps.items(): app.add_typer(t, name=v)`), add:

```python
    app.add_typer(_config_commands.config_app, name="config", rich_help_panel="CLI")
```

In `render_cli.py`, after the `default_config.yml` emission line from Task 1, add:

```python
    render("_generated/config_commands.py.jinja", gen / "config_commands.py")
```

- [ ] **Step 5: Run the tests**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja \
        src/phantasos/generator/cli/templates/_generated/app.py.jinja \
        src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted.py
git commit -m "feat(cli-gen): config init/show meta-commands in dedicated CLI help panel"
```

---

### Task 5: Emitted-suite test, pydantic dep, full-suite sweep

**Files:**
- Create: `src/phantasos/generator/cli/cli_overrides/tests/test_config.py.jinja`
- Modify: `src/phantasos/generator/cli/scaffold_context.py:8-10` (`_CLI_DEPS`)
- Test: `tests/test_cli_scaffold.py` (dependency assertions, if any reference `_CLI_DEPS`)

- [ ] **Step 1: Add the emitted CLI's own config tests**

Create `src/phantasos/generator/cli/cli_overrides/tests/test_config.py.jinja`:

```python
"""Config-file behavior of the generated CLI (defaults sync + config commands)."""

import yaml
from typer.testing import CliRunner

from {{ package }}._generated import config as _config
from {{ package }}.main import app


def test_packaged_defaults_match_models() -> None:
    data = yaml.safe_load(_config.packaged_default_text())
    assert _config.ConfigFile.model_validate(data) == _config.ConfigFile()


def test_config_init_and_show(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    # config was cached at import (possibly from the developer's real homedir);
    # reset so this test sees the isolated HOME.
    _config.load_config.cache_clear()
    runner = CliRunner()
    assert runner.invoke(app, ["config", "init"]).exit_code == 0
    assert (tmp_path / ".{{ distribution }}" / "config.yml").exists()
    assert runner.invoke(app, ["config", "init"]).exit_code == 1
    assert runner.invoke(app, ["config", "init", "--force"]).exit_code == 0
    res = runner.invoke(app, ["config", "show"])
    assert res.exit_code == 0
    assert "merged from" in res.output
```

(Do NOT test the `--output` default here: it was baked at import from the
developer's environment. That behavior is covered deterministically in
phantasos's controlled fixture, Task 3.)

- [ ] **Step 2: Add pydantic to `_CLI_DEPS`**

In `scaffold_context.py`:

```python
_CLI_DEPS = [
    "typer>=0.12", "rich>=13", "pyyaml>=6", "python-dotenv>=1.0", "jmespath>=1.0",
    "pydantic>=2.11",
]
```

(pyproject is SCAFFOLD-OWNED — overwritten every `cli build` — so existing CLIs
pick this up on rebuild.)

- [ ] **Step 3: Full suite + lint + types**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests && UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src`
Expected: all pass / clean. If a `tests/test_cli_scaffold.py` assertion enumerates the dependency list, update it to include `pydantic>=2.11`.

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/generator/cli/cli_overrides/tests/test_config.py.jinja \
        src/phantasos/generator/cli/scaffold_context.py tests/
git commit -m "feat(cli-gen): emitted config test suite + explicit pydantic dependency"
```

---

### Task 6: Gated real-SDK test + real CLI rebuild verification

**Files:**
- Modify: `tests/test_cli_emitted_real.py` (append)
- Regenerates: `/home/ubuntu/git/prisma-browser-cli` (sibling repo — do NOT commit it)

- [ ] **Step 1: Add the gated test**

Append to `tests/test_cli_emitted_real.py` (the `real_cli` fixture already exists; `CliRunner` is imported inside existing tests — follow that pattern):

```python
def test_real_config_init_and_show(real_cli, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("prisma_browser_cli.main")
    r = CliRunner()
    assert r.invoke(main.app, ["config", "init"]).exit_code == 0
    assert (tmp_path / ".prisma-browser-cli" / "config.yml").exists()
    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "pager" in res.output and "merged from" in res.output
```

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/test_cli_emitted_real.py -q`
Expected: PASS (skips if the sibling SDK is missing).

- [ ] **Step 2: Rebuild the real CLI and verify by hand**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run phantasos cli build prisma-browser
cd /home/ubuntu/git/prisma-browser-cli
export UV_PROJECT_ENVIRONMENT=/tmp/prisma-browser-cli-venv
uv sync
uv run prisma-browser-cli --help          # config group in its own "CLI" panel
uv run prisma-browser-cli config init     # writes ~/.prisma-browser-cli/config.yml
uv run prisma-browser-cli config show     # effective config + sources
uv run prisma-browser-cli show device-group --help   # --pager/--no-pager listed
```

Also run the emitted suite inside the CLI project: `uv run pytest tests/ -q` — the new `test_config.py` must pass there.

Expected: all of the above behave as designed. Pager engagement itself needs a real TTY (this session has none) — note in the report that `pager.enabled: true` + a tall `show application --all` is the user's manual acceptance check.

- [ ] **Step 3: Restore homedir state**

If `config init` was run with real `$HOME` during manual verification, remove `~/.prisma-browser-cli/config.yml` unless the user wants to keep it — report what was left behind.

- [ ] **Step 4: Commit (phantasos repo only)**

```bash
git add tests/test_cli_emitted_real.py
git commit -m "test(gated): config init/show against the real generated CLI"
```

---

### Task 7: Wrap-up — full gate + memory

- [ ] **Step 1: Full verification (paste real output in the report)**

```bash
cd /home/ubuntu/git/phantasos
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run pytest tests/ -q
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run ruff check src tests
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv uv run mypy src
```

- [ ] **Step 2: Update project memory** — append the feature completion (date, HEAD, key decisions: import-time config load, `~/.{distribution}/config.yml`, auto-threshold pager, config init/show, what's deferred: environments list) to the `prisma-browser-cli-generator-design` memory file. Update the TODO entries in `docs/TODO.md`: mark "Pager Output" addressed (and reference the spec); note "User-Facing CLI Configuration File" now has its foundation (config file + schema) with multi-env still open.

- [ ] **Step 3: Handoff** — report: branch/HEAD, sibling `prisma-browser-cli` regenerated but uncommitted, the manual TTY pager acceptance check for the user.

---

## Self-review (done at planning time)

- **Spec coverage:** schema/load/warnings → T1; pager mechanics + yaml fix → T2; flag wiring + reserved name → T3; meta-commands + panel → T4; deps + emitted suite + sync-lock test → T5 (sync test also in T1 phantasos-side); gated real test + rebuild → T6; TODO/memory updates → T7. The spec's "out of scope" items have no tasks (correct).
- **Methodology check:** all behavioral tests go through the emitted package; the only mock is `facade.Client.from_env` (T3); `_AutoPager` tests use real subprocesses (`tee`), not mocks; gated tests follow the existing skip pattern.
- **Type consistency:** `load_config() -> tuple[ConfigFile, tuple[str, ...], tuple[str, ...]]` used consistently (T1 def; T4 `config show` unpacks 3-tuple; tests index `[1]`/`[2]`). `maybe_paged(flag: bool | None)` (T2 def, T3 runtime call). `default_output()` (T1 def, T3 commands template). `_write_user_config` helper defined in T1, reused in T2/T3 tests (same file).
- **Known risk flagged to implementer:** Task 2 Step 2 note — the yaml regression test passes before the refactor (print already has no trailing blank); it exists to lock the `end=""` behavior through the console move in Step 3. The real red/green for T2 is the `_AutoPager` tests.
