# CLI environment resolution: honest `show` + debug logging — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make a generated CLI's `environment show` report the *effective* settings (env-var overrides + sources) instead of the raw config file, backed by one shared resolver that the client also uses, plus opt-in debug logging of overrides.

**Architecture:** Add a pure `resolve_effective(name, *, env=None) -> list[_EffField]` in the emitted `config.py` that applies the exact env-var precedence the client uses today, tagging each field with a `_Source` enum. Refactor `runtime.py`'s `_client()`/`_preflight_connection()` to consume it (deleting their inline override loops) and make selection a single `_selected_environment_source()`; rewrite `environment show` to render a `FIELD | VALUE | SOURCE` table. Debug lines emit inside the shared resolver/selector.

**Tech Stack:** Python 3.11+, Jinja2 emitted templates (`generator/cli/templates/_generated/`), Typer/Rich, stdlib `logging`/`enum`, pytest via the emitted-package fixtures.

**Spec:** `docs/specs/2026-07-06-cli-env-resolution-display.md` (decisions in §9, review folds in §10). **Branch:** `bugfix/cli-env-handling`.

## Global Constraints

- **Behavior-preserving for the client:** `_client()`/`_preflight_connection()` produce the SAME values/exit-codes as today — only *how* they resolve changes. The Task-4 parity test is the guard.
- **The single-source-of-truth is only real if the inline copies are deleted:** after Task 4, `runtime.py` contains NO standalone presence/truthiness override loop; all field resolution goes through `resolve_effective`.
- **Secrets never leak:** secret *values* never appear in `environment show` output or in any log record (log var *names* + the override fact only).
- **Three precedence semantics preserved** (verbatim from spec §6): credentials = **presence** (`os.environ.get(v) is not None`; empty `CLIENT_ID=` wins and still fails the required check); connection + selection = **truthiness** (empty falls through).
- **`source` is an enum, not prose** — each consumer formats its own display string.
- **Preserve all Jinja gating** — the templates gate on `{% if has_env %}`, `{% if ir.credential_fields %}`, `{% if ir.connection_fields %}`, `{% for cv in connection_views %}`. A CLI with no credential fields must emit unchanged.
- Run tests: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest ...`. Do NOT set TMPDIR. FULL gate `nox -s gate` green before each commit. Commit SPECIFIC paths (never `git add -A`). NO `Claude-Session:` trailer. Never edit frozen oracles (`.claude/harness.toml`, `tests/golden/**`, `tests/fixtures/**`).
- **Ring-3 hard gate (Task 4):** the credential/connection parity tests run against the REAL SDK, which the offline gate SKIPS (stale SDK). Verify with a captured `PHANTASOS_ALLOW_STALE_SDK=1 uv run pytest <file> -q` and confirm behavior unchanged; the offline gate alone is insufficient there.

## File Structure

- **Modify** `src/phantasos/generator/cli/templates/_generated/config.py.jinja` — enrich `_ENV_FIELDS`; add `_Source`, `_EffField`, `resolve_effective`, `_ENV_LOG`.
- **Modify** `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — `_selected_environment_source()`; refactor `_client()`/`_preflight_connection()` to consume `resolve_effective`.
- **Modify** `src/phantasos/generator/cli/templates/_generated/environment_commands.py.jinja` — rewrite `show_environments()`.
- **Modify** `src/phantasos/generator/cli/templates/docs/guides/authentication.md.jinja` — "Where settings come from" subsection.
- **Modify** `CHANGELOG.md`.
- **Test** `tests/test_cli_emitted_environments.py` (exists; renders the auth CLI, drives `environment` commands) — append env-resolution tests. Pure resolver tests import `fakesdk_cli._generated.config`.

Interfaces added (consumed across tasks):
```
config.py:  class _Source(str, Enum): ENV STORED STORED_REF DEFAULT UNSET
            class _EffField(NamedTuple): name kind env_var client_kwarg value source secret required
            resolve_effective(name: str | None, *, env=None) -> list[_EffField]
runtime.py: _selected_environment_source() -> tuple[str | None, str]   # source ∈ {"flag","env","default","none"}
            _selected_environment() -> str | None                       # == _selected_environment_source()[0]
```

---

## Task 1: Enrich `_ENV_FIELDS` with `env_var` + `client_kwarg`

The resolver needs each credential's overriding env var and client kwarg; `_ENV_FIELDS` currently carries only `{name, secret}`. Add the two keys (the IR credential field already exposes `.env_var` and `.client_kwarg`, used at `runtime.py:149,152`). Keeps `config.py` self-contained (no IR import).

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config.py.jinja` (the `_ENV_FIELDS` block, ~lines 381-385)
- Test: `tests/test_cli_emitted_environments.py`

**Interfaces:**
- Produces: `_config._ENV_FIELDS` entries now have keys `name, secret, env_var, client_kwarg`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli_emitted_environments.py`:

```python
def test_env_fields_carry_env_var_and_client_kwarg(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        assert cfg._ENV_FIELDS, "auth build must have credential fields"
        f = cfg._ENV_FIELDS[0]
        assert set(f) >= {"name", "secret", "env_var", "client_kwarg"}
        assert isinstance(f["env_var"], str) and f["env_var"]
        assert isinstance(f["client_kwarg"], str) and f["client_kwarg"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py::test_env_fields_carry_env_var_and_client_kwarg -v`
Expected: FAIL (`KeyError`/`assert` — keys absent).

- [ ] **Step 3: Enrich the template.** Replace the `_ENV_FIELDS` block in `config.py.jinja`:

```jinja
_ENV_FIELDS: list[dict[str, Any]] = [
{%- for f in ir.credential_fields %}
    {"name": {{ f.name|tojson }}, "secret": {{ "True" if f.secret else "False" }},
     "env_var": {{ f.env_var|tojson }}, "client_kwarg": {{ (f.client_kwarg or f.name)|tojson }}},
{%- endfor %}
]
```

- [ ] **Step 4: Run tests to verify pass** (+ the existing config defaults-sync is unaffected — `_ENV_FIELDS` is not a config model)

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py tests/test_cli_emitted_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja tests/test_cli_emitted_environments.py
git commit -m "feat(cli): _ENV_FIELDS carries env_var + client_kwarg (for the shared resolver)"
```

---

## Task 2: `_Source` + `_EffField` + `resolve_effective` (pure resolver) in `config.py`

The one place the file∘env merge with attribution happens. Pure: takes an injectable `env` mapping. Applies the three precedence rules and tags each field with its `_Source`.

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config.py.jinja` (add imports `enum.Enum`, `typing.NamedTuple`/`Mapping`, a `logging.getLogger`; add the resolver after `resolve_connection`, ~line 459)
- Test: `tests/test_cli_emitted_environments.py`

**Interfaces:**
- Consumes: `_ENV_FIELDS` (Task 1), `_CONN_FIELDS`, `_raw_environments`, `_resolve_value`.
- Produces: `_Source`, `_EffField`, `resolve_effective(name, *, env=None) -> list[_EffField]`, `_ENV_LOG`.

- [ ] **Step 1: Write the failing tests** — append. These exercise the precedence as a PURE function (inject `env`):

```python
def _cfg(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = render_and_import(out, "fakesdk_cli")
    ctx.__enter__()
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    return cfg


def test_resolve_effective_env_overrides_stored(emit_cli, render_and_import, monkeypatch, tmp_path):
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    # write a named environment with a stored client_id
    envs = {"environments": {"prod": {"client_id": "stored-id"}}, "default_environment": "prod"}
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    # exported CLIENT_ID overrides the stored value (presence semantics)
    eff = {f.name: f for f in cfg.resolve_effective("prod", env={"CLIENT_ID": "env-id"})}
    assert eff["client_id"].value == "env-id"
    assert eff["client_id"].source == cfg._Source.ENV
    assert eff["client_id"].env_var == "CLIENT_ID"
    # a stored-only field reports STORED
    eff2 = {f.name: f for f in cfg.resolve_effective("prod", env={})}
    assert eff2["client_id"].value == "stored-id"
    assert eff2["client_id"].source == cfg._Source.STORED


def test_resolve_effective_empty_credential_env_wins_presence(emit_cli, render_and_import, monkeypatch, tmp_path):
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    envs = {"environments": {"prod": {"client_id": "stored-id"}}}
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    # exported-but-EMPTY CLIENT_ID wins for credentials (presence, not truthiness)
    eff = {f.name: f for f in cfg.resolve_effective("prod", env={"CLIENT_ID": ""})}
    assert eff["client_id"].value == "" and eff["client_id"].source == cfg._Source.ENV


def test_resolve_effective_stored_ref_expands(emit_cli, render_and_import, monkeypatch, tmp_path):
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    envs = {"environments": {"prod": {"client_id": "${MY_ID}"}}}
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    monkeypatch.setenv("MY_ID", "from-ref")
    eff = {f.name: f for f in cfg.resolve_effective("prod", env=dict(__import__("os").environ))}
    assert eff["client_id"].value == "from-ref"
    assert eff["client_id"].source == cfg._Source.STORED_REF


def test_resolve_effective_unset(emit_cli, render_and_import, monkeypatch, tmp_path):
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    eff = {f.name: f for f in cfg.resolve_effective(None, env={})}
    assert eff["client_id"].value is None and eff["client_id"].source == cfg._Source.UNSET
```

- [ ] **Step 2: Run to verify fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py -k resolve_effective -v`
Expected: FAIL (`_Source`/`resolve_effective` undefined).

- [ ] **Step 3: Add the resolver** to `config.py.jinja`. Ensure imports at top include `from enum import Enum`, `from typing import NamedTuple` (or `Any` already imported), `from collections.abc import Mapping`, and `import logging`. Add after `resolve_connection` (guard the whole block so a no-auth CLI omits it — mirror how `_ENV_FIELDS` is only meaningful with credential/connection fields; it is safe to always emit since it iterates possibly-empty `_ENV_FIELDS`/`_CONN_FIELDS`):

```python
_ENV_LOG = logging.getLogger("{{ package }}.env")


class _Source(str, Enum):
    ENV = "env"              # a direct exported env var
    STORED = "stored"        # literal value stored in the environment block
    STORED_REF = "stored_ref"  # stored ${VAR} reference, expanded
    DEFAULT = "default"      # a packaged/SDK default fills the gap
    UNSET = "unset"          # nothing anywhere


class _EffField(NamedTuple):
    name: str
    kind: str            # "credential" | "connection"
    env_var: str
    client_kwarg: str    # credential: how _client passes it; connection: "" (n/a)
    value: str | None
    source: _Source
    secret: bool
    required: bool


def _stored_source(raw: Any) -> _Source:
    return _Source.STORED_REF if isinstance(raw, str) and _ENV_REF_RE.match(raw) else _Source.STORED


def resolve_effective(name: str | None, *, env: Mapping[str, str] | None = None) -> list[_EffField]:
    """Effective credential + connection fields for environment ``name``, applying the
    SAME env-var precedence ``_client``/``_preflight`` use, each tagged with its source.

    ``env`` defaults to ``os.environ`` (inject a dict for pure tests). Callers that need
    ``.env`` support must load dotenv BEFORE calling (``_client`` does; ``environment
    show`` must too). Logs one DEBUG line per field whose env var displaced a stored
    value — never the value (var name + override fact only)."""
    env = os.environ if env is None else env
    block = _raw_environments().get(name) if name else None
    block = block if isinstance(block, dict) else {}
    out: list[_EffField] = []
    for f in _ENV_FIELDS:                                    # credentials — PRESENCE
        ev = env.get(f["env_var"])                           # not truthiness
        stored = _resolve_value(block.get(f["name"]), env=env)
        if ev is not None:
            value, source = ev, _Source.ENV
        elif stored is not None:
            value, source = stored, _stored_source(block.get(f["name"]))
        else:
            value, source = None, _Source.UNSET
        if source is _Source.ENV and stored is not None:
            _ENV_LOG.debug("%s: using env %s (overrides environment %r)",
                           f["name"], f["env_var"], name)
        out.append(_EffField(f["name"], "credential", f["env_var"], f["client_kwarg"],
                             value, source, bool(f["secret"]), bool(f.get("required", True))))
    for f in _CONN_FIELDS:                                   # connection — TRUTHINESS
        ev = env.get(f["env"])
        stored = _resolve_value(block.get(f["key"]), env=env)
        if ev:                                               # truthy wins
            value, source = ev, _Source.ENV
        elif stored:
            value, source = stored, _stored_source(block.get(f["key"]))
        else:
            value, source = (stored if stored is not None else None), _Source.UNSET
        if source is _Source.ENV and stored:
            _ENV_LOG.debug("%s: using env %s (overrides environment %r)",
                           f["env"], f["env"], name)
        out.append(_EffField(f["env"], "connection", f["env"], "", value, source, False, False))
    return out
```

Also update `_resolve_value` to accept the injectable `env` (default `os.environ`) so the resolver stays pure:

```python
def _resolve_value(v: Any, *, env: Mapping[str, str] | None = None) -> Any:
    env = os.environ if env is None else env
    if isinstance(v, str):
        m = _ENV_REF_RE.match(v)
        if m:
            return env.get(m.group(1))
    return v
```

> Note: `_ENV_FIELDS` has no `required` key yet — `f.get("required", True)` defaults required=True (safe; the required-check policy stays in `_client`). If the parity in Task 4 needs the real `required`, add it to `_ENV_FIELDS` there. Connection `required`/`required_for` stay read from the IR by `_preflight` (Task 4); `_EffField.required` is only used by display.

- [ ] **Step 4: Run tests to verify pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py -k resolve_effective -v && uv run nox -s gate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja tests/test_cli_emitted_environments.py
git commit -m "feat(cli): resolve_effective — pure file/env resolver with source attribution"
```

---

## Task 3: `_selected_environment_source()` — single selection function + debug log

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`_selected_environment`, ~lines 61-73)
- Test: `tests/test_cli_emitted_environments.py`

**Interfaces:**
- Produces: `_selected_environment_source() -> tuple[str | None, str]` (source ∈ `"flag"|"env"|"default"|"none"`); `_selected_environment()` returns `[0]`.

- [ ] **Step 1: Write the failing test** — append:

```python
def test_selected_environment_source(emit_cli, render_and_import, monkeypatch, tmp_path, caplog):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli._generated.runtime")
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {"environments": {"prod": {}, "staging": {}}, "default_environment": "prod"}
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        assert rt._selected_environment_source() == ("prod", "default")
        monkeypatch.setenv("FAKESDK_ENVIRONMENT", "staging")
        with caplog.at_level(logging.DEBUG, logger="fakesdk_cli.env"):
            assert rt._selected_environment_source() == ("staging", "env")
            assert rt._selected_environment() == "staging"       # [0] parity
        assert any("staging" in r.message for r in caplog.records)
        monkeypatch.setenv("FAKESDK_ENVIRONMENT", "")            # empty -> falls through
        assert rt._selected_environment_source() == ("prod", "default")
```

(The fixture's env prefix is `FAKESDK`, so the selection var is `FAKESDK_ENVIRONMENT`.)

- [ ] **Step 2: Run to verify fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py::test_selected_environment_source -v`
Expected: FAIL (`_selected_environment_source` undefined).

- [ ] **Step 3: Replace `_selected_environment`** in `runtime.py.jinja` with the single function + wrapper (keep the `{% if has_env %}` gating):

```python
def _selected_environment_source() -> tuple[str | None, str]:
    """The active environment and WHY, by precedence:
    -e flag (contextvar) > {{ env_prefix }}_ENVIRONMENT env var > default_environment.
    Source ∈ {"flag","env","default","none"}. Empty {{ env_prefix }}_ENVIRONMENT is
    treated as absent (falls through). Logs the winning source at DEBUG."""
    from . import config as _config

    flag = _SELECTED_ENV.get()
    if flag:
        name, source = flag, "flag"
    elif os.environ.get("{{ env_prefix }}_ENVIRONMENT"):
        name, source = os.environ["{{ env_prefix }}_ENVIRONMENT"], "env"
    else:
        d = _config.default_environment()
        name, source = (d, "default") if d else (None, "none")
    _config._ENV_LOG.debug("selected environment %r (source: %s)", name, source)
    return name, source


def _selected_environment() -> str | None:
    return _selected_environment_source()[0]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py -k selected_environment -v && uv run nox -s gate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted_environments.py
git commit -m "feat(cli): single _selected_environment_source() with debug log"
```

---

## Task 4: Refactor `_client()` + `_preflight_connection()` to consume `resolve_effective`

Delete the inline presence/truthiness loops; drive both from `resolve_effective`. **Behavior-preserving** — this is the acceptance criterion for the SSoT. Ring-3.

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`_preflight_connection` ~78-118; `_client` credential loop ~144-174; connection export ~175-182)
- Test: `tests/test_cli_emitted_environments.py` (parity) + existing `tests/test_cli_emitted_real.py` auth paths.

**Interfaces:**
- Consumes: `resolve_effective`, `_EffField`, `_selected_environment` (Tasks 2/3).

- [ ] **Step 1: Write the parity test** — append. It proves `resolve_effective` yields exactly what the old inline loop produced for credentials, so the refactor is behavior-preserving:

```python
def test_client_credentials_parity(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {"environments": {"prod": {"client_id": "stored", "scope": "s"}}}
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        # replicate the OLD _client credential resolution and compare to the new resolver
        import os as _os
        env = {"CLIENT_ID": "envid"}
        old = {}
        legacy_env = cfg.resolve_environment("prod")
        for f in cfg._ENV_FIELDS:
            ev = env.get(f["env_var"])
            val = ev if ev is not None else legacy_env.get(f["name"])
            if val is not None:
                old[f["client_kwarg"]] = val
        new = {}
        for e in cfg.resolve_effective("prod", env=env):
            if e.kind == "credential" and e.value is not None:
                new[e.client_kwarg] = e.value
        assert new == old   # identical overrides dict -> identical client behavior
```

- [ ] **Step 2: Run to verify it passes ALREADY** (it compares two computations; it should pass before the refactor and MUST keep passing after — it's the regression guard, not a red-first test)

Run: `PHANTASOS_ALLOW_STALE_SDK=1 UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py::test_client_credentials_parity -v`
Expected: PASS (guards the refactor).

- [ ] **Step 3: Refactor `_client()` credential loop.** Replace lines 145-157 (from `env = _config.resolve_environment(name) if name else {}` through the `for f in _ir().credential_fields:` loop body) with a resolve_effective-driven loop (KEEP the `missing`/required assembly and the `{%- if ir.credential_fields %}` gating):

```python
    overrides: dict[str, Any] = {}
    missing: list[str] = []
    _req = {f.name: f.required for f in _ir().credential_fields}   # required stays IR-driven
    for e in _config.resolve_effective(name):
        if e.kind != "credential":
            continue
        if e.value is not None:
            overrides[e.client_kwarg] = e.value
        if _req.get(e.name) and not e.value:
            missing.append(e.env_var)
```

Replace the connection export loop (175-182) with resolve_effective (KEEP the `{%- if ir.connection_fields %}` gating):

```python
    for e in _config.resolve_effective(name):
        if e.kind == "connection" and e.env_var not in os.environ and e.value is not None:
            os.environ[e.env_var] = e.value
```

Refactor `_preflight_connection` (78-118): keep the needed-check reading `_ir().connection_fields` (for `required`/`required_for`/`flag`), but source the VALUE from `resolve_effective` instead of the inline `os.environ.get(f.env) or conn_resolved.get(f.env)`:

```python
    name = _selected_environment()
    eff = {e.env_var: e for e in _config.resolve_effective(name) if e.kind == "connection"}
    for f in _ir().connection_fields:
        needed = f.required or (cmd.subpackage is not None and cmd.subpackage in f.required_for)
        if not needed:
            continue
        val = eff[f.env].value if f.env in eff else None
        if not val:
            ...  # unchanged fail block (flag/why/headline/hint)
```

- [ ] **Step 4: Verify behavior unchanged (RING-3 HARD GATE).** The offline gate skips real-SDK auth; run the real auth paths explicitly and confirm no change:

Run: `PHANTASOS_ALLOW_STALE_SDK=1 UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py tests/test_cli_emitted_real.py tests/test_cli_emitted_connection.py -q`
Expected: PASS with the SAME counts as before the refactor (capture both). Then `uv run nox -s gate` (offline) green. **Confirm `runtime.py` no longer contains a standalone `os.environ.get(...) or ...` / presence override loop** (grep the emitted file).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted_environments.py
git commit -m "refactor(cli): _client/_preflight consume resolve_effective (delete inline override loops)"
```

---

## Task 5: Rewrite `environment show` — `FIELD | VALUE | SOURCE` table

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/environment_commands.py.jinja` (`show_environments`, ~146-176)
- Test: `tests/test_cli_emitted_environments.py`

**Interfaces:**
- Consumes: `resolve_effective`, `_Source` (Task 2), `_selected_environment_source` (Task 3).

- [ ] **Step 1: Write the failing tests** — append (drive the real `environment show` via `CliRunner`):

```python
def test_environment_show_reflects_env_override(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {"environments": {"prod": {"client_id": "stored-id", "client_secret": "sekret", "scope": "s"}},
                "default_environment": "prod"}
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        main = importlib.import_module("fakesdk_cli.main")
        # env var selects staging? no staging here — test the per-field override + reason
        monkeypatch.setenv("CLIENT_ID", "env-id")
        res = CliRunner().invoke(main.app, ["environment", "show"], env={"NO_COLOR": "1"})
        assert res.exit_code == 0
        assert "prod (active — default_environment)" in res.output
        assert "env-id" in res.output and "env CLIENT_ID" in res.output   # effective value + source
        assert "stored-id" not in res.output                              # not the overridden stored value
        assert "sekret" not in res.output and "•" in res.output           # secret masked


def test_environment_show_active_reason_env(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {"environments": {"prod": {}, "staging": {}}, "default_environment": "prod"}
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        monkeypatch.setenv("FAKESDK_ENVIRONMENT", "staging")
        main = importlib.import_module("fakesdk_cli.main")
        res = CliRunner().invoke(main.app, ["environment", "show"], env={"NO_COLOR": "1"})
        assert "staging (active — via FAKESDK_ENVIRONMENT)" in res.output
```

- [ ] **Step 2: Run to verify fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py -k environment_show -v`
Expected: FAIL (old output; no reason marker / no effective block).

- [ ] **Step 3: Rewrite `show_environments()`** in `environment_commands.py.jinja`:

```python
@environment_app.command("show")
def show_environments() -> None:
    """List environments; for the active one, show effective settings and where each
    value comes from (env var vs stored vs default). Secret values are masked."""
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True))   # mirror _client so show == behavior
    except ModuleNotFoundError:
        pass
    environments = _config._raw_environments()
    if not environments:
        _diag.info("no environments defined")
        return
    active, source = _rt._selected_environment_source()
    reason = {"env": "via {{ env_prefix }}_ENVIRONMENT", "default": "default_environment",
              "flag": "via --environment", "none": ""}.get(source, "")
    for name in environments:
        mark = f" (active — {reason})" if name == active and reason else (" (active)" if name == active else "")
        typer.echo(f"{name}{mark}")
    if active in environments:
        typer.echo(f"\nActive environment '{active}' — effective settings:")
        rows = _config.resolve_effective(active)
        typer.echo(f"  {'FIELD':<14} {'VALUE':<20} SOURCE")
        for e in rows:
            shown = "••••• (hidden)" if e.secret else (e.value if e.value is not None else "(default)" if e.source is _config._Source.DEFAULT else "(unset)")
            src = {
                _config._Source.ENV: f"env {e.env_var}",
                _config._Source.STORED: f"environment '{active}'",
                _config._Source.STORED_REF: f"environment '{active}' (via ${{...}})",
                _config._Source.DEFAULT: "default",
                _config._Source.UNSET: "unset",
            }[e.source]
            # note when an env var displaced a stored value
            if e.source is _config._Source.ENV and isinstance(_config._raw_environments().get(active), dict) \
               and _config._raw_environments()[active].get(e.name if e.kind == "credential" else e.env_var) is not None:
                src += f" (overrides environment '{active}')"
            typer.echo(f"  {e.name:<14} {str(shown):<20} {src}")
    elif active is not None:
        _diag.fail(f"active environment '{active}' is not defined (run 'environment show')", code=2)
    else:
        _diag.info("no active environment — auth falls back to environment variables")
```

> The `${{...}}` in the STORED_REF label is a placeholder for the literal `${VAR}` — render it as the literal string `(via ${VAR})` in the template (escape the Jinja/format braces so the emitted Python prints `environment '<name>' (via ${VAR})`). Implementer: verify the emitted line reads `(via ${VAR})`.

- [ ] **Step 4: Run tests to verify pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/test_cli_emitted_environments.py -k environment_show -v && uv run nox -s gate`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/environment_commands.py.jinja tests/test_cli_emitted_environments.py
git commit -m "feat(cli): environment show reports effective settings + sources (masked secrets)"
```

---

## Task 6: Dedicated "Environments & variables" docs page (authored against the finished impl)

A dedicated generated-CLI docs page (not just an authentication.md subsection) that explains how named environments work, the exact precedence order applied, AND lists **every** environment variable the CLI reads. Emitted only for CLIs with environments (`has_env`), like the authentication guide. Author it last, so it reflects the real resolver/`show` behavior built in Tasks 1-5.

**Files:**
- Create: `src/phantasos/generator/cli/templates/docs/guides/environments.md.jinja`
- Modify: `src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja` (add the nav entry under Guides, gated on `has_env`)
- Modify: `src/phantasos/generator/cli/templates/docs/guides/authentication.md.jinja` (replace any full precedence prose with a one-line pointer to the new page — DRY)
- Test: `tests/cli/test_docs_emitted.py`

**Interfaces:**
- Consumes (docs render ctx, confirmed in `render_cli.py:586-601`): `ir` (`ir.credential_fields[].env_var`/`.name`/`.secret`), `connection_views` (`cv.env`/`cv.header`), `env_prefix`, `distribution`, `has_env`.

- [ ] **Step 1: Write the failing tests** — append to `tests/cli/test_docs_emitted.py`:

```python
def test_environments_guide_lists_vars_and_precedence(emit_cli):
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    env_md = (out / "docs" / "guides" / "environments.md").read_text()
    # precedence / order is documented (both chains)
    assert "FAKESDK_ENVIRONMENT" in env_md and "default_environment" in env_md
    assert "--environment" in env_md          # -e is the top of the selection chain
    # every credential env var the CLI reads is listed
    import ast
    cfg = (out / "fakesdk_cli" / "_generated" / "config.py").read_text()
    env_map_vars = set(__import__("re").findall(r'"(FAKESDK_[A-Z0-9_]+)"', cfg))
    for var in env_map_vars:                   # config vars (logging/cache/output/...)
        assert var in env_md, f"{var} missing from environments.md"
    assert "CLIENT_ID" in env_md               # credential var (from the IR)
    assert "FAKESDK_ENVIRONMENT" in env_map_vars or "FAKESDK_ENVIRONMENT" in env_md

def test_environments_guide_absent_without_env(emit_cli):
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"))  # no auth -> no env
    assert not (out / "docs" / "guides" / "environments.md").exists()

def test_environments_guide_in_nav(emit_cli):
    import yaml
    out = emit_cli(docs=CliDocsConfig(showcase_object="widget"), auth=True)
    cfg = yaml.safe_load((out / "mkdocs.yml").read_text())
    guides = next(s["Guides"] for s in cfg["nav"] if "Guides" in s)
    assert any("environments.md" in (next(iter(g.values())) if isinstance(g, dict) else g) for g in guides)
```

The `env_map_vars` regex reads the REAL `_ENV_MAP` (+`_ENVIRONMENT`) keys from the emitted `config.py`, so the page can't silently omit a config variable — this is the drift guard for "all env vars listed".

- [ ] **Step 2: Run to verify fail**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/cli/test_docs_emitted.py -k environments_guide -v`
Expected: FAIL (page not emitted).

- [ ] **Step 3: Create the page** `docs/guides/environments.md.jinja`:

```jinja
# Environments & variables

`{{ distribution }}` reads its connection and credential settings from **named
environments** (stored in `~/.{{ distribution }}/environments.yml`) and from
**environment variables**, with environment variables taking precedence. Manage
environments with `{{ distribution }} environment create|activate|show|delete`.

## Which environment is active (selection order)

The active environment is chosen by this order — the first that is set wins:

1. `--environment/-e <name>` on the command
2. the `{{ env_prefix }}_ENVIRONMENT` environment variable (an empty value is ignored)
3. the `default_environment` recorded by `environment activate`

`{{ distribution }} environment show` marks the active one and says *why*
(e.g. `staging (active — via {{ env_prefix }}_ENVIRONMENT)`).

## How each value resolves (override order)

For every field, the effective value is the first of:

1. its **environment variable** (exported, or from a `.env` file) — wins
2. the value **stored in the active environment** (a `${VAR}` reference is expanded)
3. a packaged **default**, else unset

`environment show` prints the effective value and its source per field (secret
values are masked). One asymmetry to know: an exported **credential** variable wins
**even if empty** (and then the required-field check fails); an exported
**region/environment** variable wins only when **non-empty**.

## Environment variables

**Selection**

| Variable | Effect |
| --- | --- |
| `{{ env_prefix }}_ENVIRONMENT` | selects the active environment (overrides `default_environment`) |

**Credentials**

| Variable | Field |{% if false %}{% endif %}
| --- | --- |
{% for f in ir.credential_fields %}| `{{ f.env_var }}` | `{{ f.name }}`{% if f.secret %} (secret) {% endif %} |
{% endfor %}
{%- if ir.connection_fields %}
**Connection**

| Variable | Field |
| --- | --- |
{% for cv in connection_views %}| `{{ cv.env }}` | `{{ cv.header }}` |
{% endfor %}
{%- endif %}
**Configuration** (see the [Configuration guide](../configuring.md) and `config show`)

| Variable | Setting |
| --- | --- |
| `{{ env_prefix }}_LOGGING_LEVEL` | log verbosity (`info`/`debug`/`trace`) |
{% if ir.credential_fields %}| `{{ env_prefix }}_CACHE_ENABLED` | token cache on/off |
| `{{ env_prefix }}_CACHE_DIR` | token cache directory |
{% endif %}

## Verify what's effective

- `{{ distribution }} environment show` — the effective value + source per field.
- `{{ distribution }} show cli log --level debug` — logs which source won each override.
```

> Implementer: the exact `_ENV_MAP` set is authoritative — after rendering, run the Step-1 drift test; if it names a `{{ env_prefix }}_*` variable the Configuration table omits (e.g. an output var), ADD that row. Do NOT guess the list; make the test green against the real emitted `config.py`.

- [ ] **Step 4: Wire the nav** in `mkdocs.yml.jinja` (Guides section, after the auth entry):

```jinja
{% if has_env %}      - Environments & variables: guides/environments.md
{% endif %}
```

And in `authentication.md.jinja`, replace any full precedence table with a pointer:

```jinja
> **Where do settings come from?** Environment variables override stored environment
> values. See **[Environments & variables](environments.md)** for the full precedence
> order and every variable `{{ distribution }}` reads.
```

- [ ] **Step 5: Run tests to verify pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run pytest tests/cli/test_docs_emitted.py -k "environments_guide or guides_always" -v && uv run nox -s gate`
Expected: PASS (incl. the drift test — every `_ENV_MAP` var appears on the page).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/docs/guides/environments.md.jinja src/phantasos/generator/cli/templates/docs/mkdocs.yml.jinja src/phantasos/generator/cli/templates/docs/guides/authentication.md.jinja tests/cli/test_docs_emitted.py
git commit -m "docs(cli): dedicated Environments & variables page (precedence + every env var)"
```

---

## Task 7: CHANGELOG + whole-feature verification

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: CHANGELOG `## [Unreleased] ### Fixed`:**

```markdown
- **`environment show` now reports EFFECTIVE settings** — when an environment variable
  (or `.env`) overrides a named environment's stored value, `environment show` shows the
  value that will actually be used and its source (a `FIELD | VALUE | SOURCE` table;
  secret values masked), and marks the truly-active environment with why (`via
  <PREFIX>_ENVIRONMENT` / `default_environment`). Previously it displayed the raw config
  file and ignored env-var overrides. Overrides are also logged at debug (`show cli log
  --level debug`). Resolution is now a single `resolve_effective` used by both the client
  and `show`, so display can't drift from behavior. New generated-CLI docs page
  **Environments & variables** documents the precedence order and every variable the CLI reads.
```

- [ ] **Step 2: Whole-feature verification**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/env uv run nox -s gate` (green) and `uv run nox -s docs` (strict; the new page + nav build under mkdocs `--strict`). Render the fakesdk CLI with auth AND without auth and `ast.parse` each emitted `config.py`/`runtime.py`/`environment_commands.py` (all parse — the no-auth build must be unaffected, and `environments.md` must be ABSENT there). Run `PHANTASOS_ALLOW_STALE_SDK=1 uv run pytest tests/test_cli_emitted_environments.py tests/test_cli_emitted_real.py -q` green with unchanged auth behavior.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(cli): CHANGELOG for env-resolution fix + environments docs page"
```

---

## Self-Review

**Spec coverage:** §3.1 resolver → Task 2 (+ Task 1 enrichment); §3.2 selection → Task 3; §3.3 debug logging → inside Tasks 2/3; §3.1 acceptance (delete inline loops, parity) → Task 4; §4.1 show output → Task 5; §4.2 debug output → Tasks 2/3 (caplog) + Task 5; §4.3 docs → Task 6 + Task 7; §6 subtleties (presence vs truthiness, ${VAR} ref, masking, no-active) → Tasks 2/5; §7 testing → each task's tests + Task 4 parity + Task 5 no-secret. All covered. **Scope addition beyond the spec** (user request, folded in): Task 6 promotes the §4.3 authentication.md *subsection* to a **dedicated `environments.md` page** that documents the full precedence order and lists **every** env var the CLI reads (selection + credential + connection + config), with a drift test that reads the real `_ENV_MAP` from the emitted `config.py`.

**Placeholder scan:** the only intentional call-out is the `(via ${VAR})` literal-escape note in Task 5 Step 3 (flagged, not a TODO). No "add error handling"/"similar to"/TBD.

**Type consistency:** `_EffField(name, kind, env_var, client_kwarg, value, source, secret, required)`, `_Source.{ENV,STORED,STORED_REF,DEFAULT,UNSET}`, `resolve_effective(name, *, env=None)`, `_selected_environment_source() -> (name, source)` used identically across Tasks 2-6.

**Coverage-drop watch:** Task 4 is the risk (behavior-preserving refactor of the auth path) — guarded by the parity test (Step 1) + the ring-3 real-SDK run (Step 4). If parity can't be shown for any field, STOP — do not ship a resolver that diverges from the old `_client`.
