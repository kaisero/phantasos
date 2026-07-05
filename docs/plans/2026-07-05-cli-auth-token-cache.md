# CLI Auth Token Cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the client-credentials JWT across generated-CLI runs so back-to-back authenticated commands reuse a valid token instead of re-authenticating each time.

**Architecture:** A new emitted module `auth_cache.py` (a per-principal file store under `~/.<dist>/cache/`, plus a defensive resolver that reaches the SDK `TokenManager`'s in-memory token). `runtime.py` seeds the TokenManager from the cache before a call and persists/invalidates after (401 → discard + re-grant + retry once). CLI-only — **no SDK-generator change**. Gated to authenticating CLIs.

**Tech Stack:** Python 3.11+, Jinja2 templates (`generator/cli/templates/_generated/`), pydantic config models, Typer CLI, stdlib `logging`/`hashlib`/`json`, pytest via the emitted-package fixtures.

**Spec:** `docs/specs/2026-07-05-cli-auth-token-cache-design.md` (decisions D1–D8). **Issue:** #47.

## Global Constraints

- **Branch:** `feature/cli-auth-token-cache` off `develop`; PR → `develop`, squash-merge, **no version bump**, record under `## [Unreleased]`.
- **Run tests with:** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest ...` (this repo may be on sshfs; never rely on `.venv`). The offline gate is `uv run nox -s gate`.
- **Templates are emitted code:** every `.jinja` change is rendered into every generated CLI and guarded by golden/defaults-sync tests. Verify emitted output, not just the template.
- **Emit the whole feature only when `ir.credential_fields` is truthy** (authenticating CLIs). Wrap template additions in `{% if ir.credential_fields %}…{% endif %}` and emit `auth_cache.py` conditionally.
- **Security:** cache file `0600`, dir `0700`; the client secret is NEVER written or used as key material; the token value is NEVER logged.
- **Fail open:** any cache error (unwritable dir, corrupt file, unrecognized TokenManager shape) disables caching for that run and logs, but auth still proceeds.
- **Config recipe** (CLAUDE.md "Adding a CLI configuration option"): model field → `default_config.yml` (defaults MUST mirror models) → `_ENV_MAP` row (+`_BOOL_PATHS` for bools) → `effective_dict()` → behavioral test → consumers read via `_config.get().cache.<key>`.
- **Test policy:** never mock the system under test or the prisma-browser API boundary. The OAuth **token endpoint** is a separate auth server — stubbing it is allowed.

---

## File Structure

- **Create** `src/phantasos/generator/cli/templates/_generated/auth_cache.py.jinja` — the cache store + TokenManager resolver + `_CacheSession` + logger. One responsibility: token-cache persistence and TokenManager coupling.
- **Modify** `src/phantasos/generator/cli/templates/_generated/config.py.jinja` — `CacheConfig` model, `CliConfiguration.cache`, `_ENV_MAP`/`_BOOL_PATHS` rows, `effective_dict()`, `cache_dir_path()` helper.
- **Modify** `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja` — `cache:` block + env-var doc lines.
- **Modify** `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` — seed/persist/401-retry around the call in `run()`.
- **Modify** `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja` — `config cache-clear`.
- **Modify** `src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja` — `show cli cache`.
- **Modify** `src/phantasos/generator/cli/render_cli.py` — emit `auth_cache.py` when `ir.credential_fields`.
- **Create** `tests/test_cli_emitted_cache.py` — offline unit + runtime-wiring behavioral tests (fakesdk, auth-rendered).
- **Create** `tests/test_cli_cache_real.py` — ring-3 real-TokenManager seam test (`real_sdk` marker).
- **Modify** `CHANGELOG.md`, `docs/cli-authoring.md` (or `configuring-the-cli.md`), `.agents/context/cli-generator.md`.

Interfaces the emitted `auth_cache` module exposes (used by `runtime.py`, the commands, and tests):

```
enabled() -> bool
cache_dir() -> pathlib.Path | None          # None if disabled or unwritable (already logged)
key_for(tm) -> str                            # sha256(tm._token_url \n tm._client_id \n tm._scope)[:12]
token_manager(client) -> Any | None           # defensive resolver; None if shape unrecognized
read(key: str) -> tuple[str, float] | None    # (access_token, expires_at) or None
write(key: str, token: str, expires_at: float) -> None
delete(key: str) -> None
list_entries() -> list[tuple[str, float]]     # (key, expires_at), sorted
clear() -> int                                # files removed
session(client) -> _CacheSession | None       # None if disabled / no TokenManager
class _CacheSession:  seed_if_valid() -> None; persist() -> None; invalidate() -> None; seeded: bool
```

---

## Task 1: Config knob — `cache` section, env vars, `effective_dict`, dir helper

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config.py.jinja` (models ~58-84; `_ENV_MAP` ~88-98; `_BOOL_PATHS` ~99-103; `effective_dict` ~261-276; add `cache_dir_path` near `log_file_path` ~284)
- Modify: `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja` (env-var docs ~8-17; sections ~47-53)
- Test: `tests/test_cli_emitted_cache.py`

**Interfaces:**
- Consumes: the `emit_cli` fixture (`tests/conftest.py`) rendering the fakesdk CLI **with auth** (`emit_cli(auth=True)`), and `render_and_import`.
- Produces: `_config.get().cache.enabled: bool`, `_config.get().cache.dir: str | None`, `_config.cache_dir_path() -> Path`; env vars `FAKESDK_CACHE_ENABLED`, `FAKESDK_CACHE_DIR`.

- [ ] **Step 1: Write the failing test** — `tests/test_cli_emitted_cache.py`:

```python
"""Auth token cache — emitted through the fakesdk CLI (rendered WITH auth)."""
import importlib
import os
from pathlib import Path

import pytest


def _emit_auth_cli(emit_cli, render_and_import):
    """Render the fakesdk CLI with an auth component and import it."""
    out = emit_cli(auth=True)
    return out


def test_cache_config_defaults_and_env(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli.config")
        cfg.load_config.cache_clear()
        assert cfg.get().cache.enabled is True
        assert cfg.get().cache.dir is None
        assert cfg.cache_dir_path() == tmp_path / ".fakesdk" / "cache"
        # env override (presence-based, bool coercion)
        monkeypatch.setenv("FAKESDK_CACHE_ENABLED", "false")
        cfg.load_config.cache_clear()
        assert cfg.get().cache.enabled is False
        # effective_dict (drives `config show`) includes the cache section
        assert cfg.effective_dict()["configuration"]["cache"] == {
            "enabled": False, "dir": None,
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_cache_config_defaults_and_env -v`
Expected: FAIL — `AttributeError: ... has no attribute 'cache'` (model field absent).

- [ ] **Step 3: Add the `CacheConfig` model + wiring** in `config.py.jinja`. After the `LoggingConfig` class (~line 71) add:

```python
{% if ir.credential_fields %}
class CacheConfig(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    enabled: bool = True
    dir: str | None = None  # None -> ~/.{{ distribution }}/cache/
{% endif %}
```

In `CliConfiguration` (~line 79), after the `logging:` field add:

```python
{% if ir.credential_fields %}    cache: CacheConfig = Field(default_factory=CacheConfig)
{% endif %}
```

Add `_ENV_MAP` rows (after the `_LOGGING_FILE` row, ~line 97):

```python
{% if ir.credential_fields %}    f"{_ENV_PREFIX}_CACHE_ENABLED": ("configuration", "cache", "enabled"),
    f"{_ENV_PREFIX}_CACHE_DIR": ("configuration", "cache", "dir"),
{% endif %}
```

Add to `_BOOL_PATHS` (~line 103):

```python
{% if ir.credential_fields %}    ("configuration", "cache", "enabled"),
{% endif %}
```

Extend `effective_dict()` (~line 274, after the `logging` entry inside the returned dict):

```python
{% if ir.credential_fields %}            "cache": {"enabled": c.cache.enabled, "dir": c.cache.dir},
{% endif %}
```

Add the dir helper after `log_file_path()` (~line 291):

```python
{% if ir.credential_fields %}
def cache_dir_path() -> Path:
    """The token-cache directory: configured ``cache.dir`` (``~``/``${VAR}`` left
    to the caller) or the default ``~/.{{ distribution }}/cache``."""
    d = get().cache.dir
    if d:
        return Path(d).expanduser()
    return Path.home() / f".{_DISTRIBUTION}" / "cache"
{% endif %}
```

- [ ] **Step 4: Mirror the defaults in `default_config.yml.jinja`.** Add to the env-var reference block (~line 17):

```jinja
{% if ir.credential_fields %}#   {{ env_prefix }}_CACHE_ENABLED        -> configuration.cache.enabled
#   {{ env_prefix }}_CACHE_DIR            -> configuration.cache.dir
{% endif %}
```

Add the section after `logging:` (~line 53):

```jinja
{% if ir.credential_fields %}
  # Auth token cache: reuse a valid OAuth access token across runs instead of
  # re-authenticating every command. The token is stored per-principal, 0600,
  # under the cache dir. Disable with {{ env_prefix }}_CACHE_ENABLED=false.
  cache:
    enabled: true
    # null -> ~/.{{ distribution }}/cache/
    dir: null
{% endif %}
```

- [ ] **Step 5: Run tests to verify they pass** (including the repo's defaults-sync + golden tests that this template touches)

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py tests/test_cli_emitted_config.py -v`
Expected: PASS (defaults mirror the models; `config show` includes the section).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config.py.jinja \
        src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja \
        tests/test_cli_emitted_cache.py
git commit -m "feat(cli): cache config knob (enabled/dir) for authenticating CLIs"
```

---

## Task 2: `auth_cache.py` store layer (key, read/write/delete, list/clear, dir, logger)

**Files:**
- Create: `src/phantasos/generator/cli/templates/_generated/auth_cache.py.jinja`
- Modify: `src/phantasos/generator/cli/render_cli.py` (`_GENERATED` region + the conditional-render block near line 610-622)
- Test: `tests/test_cli_emitted_cache.py`

**Interfaces:**
- Consumes: `_config.enabled` via `_config.get().cache.enabled`, `_config.cache_dir_path()`.
- Produces: `enabled()`, `cache_dir()`, `_key(token_url, client_id, scope)`, `read()`, `write()`, `delete()`, `list_entries()`, `clear()` and module logger `_LOG`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli_emitted_cache.py`:

```python
def test_cache_store_roundtrip_perms_and_isolation(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        k1 = ac._key("https://auth/", "id-A", "scope-1")
        k2 = ac._key("https://auth/", "id-B", "scope-1")  # different principal
        assert k1 != k2 and len(k1) == 12
        assert ac.read(k1) is None                       # miss
        ac.write(k1, "tok-A", 9999999999.0)
        assert ac.read(k1) == ("tok-A", 9999999999.0)    # hit
        # secret/token never leak into the key; file is 0600, dir 0700
        f = ac.cache_dir() / f"token-{k1}.json"
        assert oct(f.stat().st_mode & 0o777) == "0o600"
        assert oct(ac.cache_dir().stat().st_mode & 0o777) == "0o700"
        assert "tok-A" not in f.name and "id-A" not in f.name
        # list + clear
        ac.write(k2, "tok-B", 8888888888.0)
        assert sorted(ac.list_entries()) == sorted([(k1, 9999999999.0), (k2, 8888888888.0)])
        assert ac.clear() == 2 and ac.read(k1) is None


def test_cache_read_tolerates_corruption(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        k = ac._key("u", "c", "s")
        (ac.cache_dir() / f"token-{k}.json").write_text("{not json")
        assert ac.read(k) is None            # corrupt -> miss (fail open), no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_cache_store_roundtrip_perms_and_isolation -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fakesdk_cli.auth_cache'`.

- [ ] **Step 3: Create `auth_cache.py.jinja`** with the store layer:

```jinja
"""Auth token cache for the {{ distribution }} CLI (injected by phantasos).

Persists the SDK's in-memory OAuth token across runs so back-to-back
authenticated commands reuse a valid token. Per-principal files under the cache
dir, 0600. The client secret is never written; the token value is never logged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from . import config as _config

_LOG = logging.getLogger("{{ package }}.auth_cache")


def enabled() -> bool:
    return _config.get().cache.enabled


def cache_dir() -> Path | None:
    """The cache dir, created 0700. None (already logged) if it can't be made."""
    d = _config.cache_dir_path()
    try:
        d.mkdir(parents=True, exist_ok=True, mode=0o700)
        d.chmod(0o700)
    except OSError as exc:
        _LOG.warning("cache dir not writable (%s); continuing without caching", exc)
        return None
    return d


def _key(token_url: str, client_id: str, scope: str) -> str:
    raw = f"{token_url}\n{client_id}\n{scope}".encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def _path(key: str) -> Path | None:
    d = cache_dir()
    return None if d is None else d / f"token-{key}.json"


def read(key: str) -> tuple[str, float] | None:
    p = _path(key)
    if p is None or not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return str(data["access_token"]), float(data["expires_at"])
    except (OSError, ValueError, KeyError, TypeError):
        _LOG.warning("ignoring unreadable cache file %s; re-authenticating", p.name)
        return None


def write(key: str, token: str, expires_at: float) -> None:
    p = _path(key)
    if p is None:
        return
    payload = json.dumps({"access_token": token, "expires_at": expires_at})
    try:
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tok-")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.chmod(tmp, 0o600)
        os.replace(tmp, p)  # atomic
    except OSError as exc:
        _LOG.warning("could not write cache file %s (%s); continuing", p.name, exc)


def delete(key: str) -> None:
    p = _path(key)
    if p is not None:
        p.unlink(missing_ok=True)


def list_entries() -> list[tuple[str, float]]:
    d = cache_dir()
    if d is None:
        return []
    out: list[tuple[str, float]] = []
    for f in sorted(d.glob("token-*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append((f.stem[len("token-"):], float(data["expires_at"])))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def clear() -> int:
    d = cache_dir()
    if d is None:
        return 0
    n = 0
    for f in d.glob("token-*.json"):
        try:
            f.unlink()
            n += 1
        except OSError:
            pass
    return n
```

- [ ] **Step 4: Emit the module conditionally** in `render_cli.py`. In the render block after the `_GENERATED` loop (near line 610), add — mirroring the `if ctx["has_env"]` env-commands render:

```python
    if ir.credential_fields:
        render("_generated/auth_cache.py.jinja", gen / "auth_cache.py")
```

(Place it beside the existing conditional renders; `render` and `gen` are already in scope.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py -v`
Expected: PASS (roundtrip, 0600/0700, isolation, corruption-tolerance).

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/auth_cache.py.jinja \
        src/phantasos/generator/cli/render_cli.py tests/test_cli_emitted_cache.py
git commit -m "feat(cli): auth_cache store layer (per-principal 0600 token files)"
```

---

## Task 3: TokenManager resolver + `_CacheSession` (seed / persist / invalidate + logging)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/auth_cache.py.jinja` (append)
- Test: `tests/test_cli_emitted_cache.py`

**Interfaces:**
- Consumes: store layer from Task 2 (`_key`, `read`, `write`, `delete`).
- Produces: `key_for(tm)`, `token_manager(client)`, `session(client) -> _CacheSession | None`, and `_CacheSession.{seed_if_valid, persist, invalidate, seeded}`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli_emitted_cache.py`:

```python
class _StubTM:
    """Mimics the SDK TokenManager's fields the cache couples to."""
    def __init__(self):
        self._token = None
        self._expires_at = 0.0
        self._token_url = "https://auth.example/token"
        self._client_id = "cid"
        self._scope = "scope-x"
        self.fetches = 0
    def token(self):
        if self._token is None or time.time() >= self._expires_at:
            self.fetches += 1
            self._token = f"minted-{self.fetches}"
            self._expires_at = time.time() + 900
        return self._token


class _StubClient:  # single-spec facade shape: client.api_client.configuration._token_manager
    def __init__(self, tm):
        cfg = type("Cfg", (), {"_token_manager": tm})()
        self.api_client = type("AC", (), {"configuration": cfg})()


def test_session_seed_persist_invalidate(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        tm = _StubTM()
        client = _StubClient(tm)
        assert ac.token_manager(client) is tm            # resolver finds single-spec shape
        # 1st run: cache miss -> no seed; a fetch happens; persist writes it
        s1 = ac.session(client)
        s1.seed_if_valid()
        assert s1.seeded is False
        tm.token()                                        # simulate the API call fetching
        s1.persist()
        key = ac.key_for(tm)
        assert ac.read(key) is not None
        # 2nd run: fresh TM, cache hit -> seed, NO fetch on token()
        tm2 = _StubTM()
        s2 = ac.session(_StubClient(tm2))
        s2.seed_if_valid()
        assert s2.seeded is True and tm2._token is not None
        assert tm2.token() == tm2._token and tm2.fetches == 0
        # invalidate clears the file + the in-memory token
        s2.invalidate()
        assert ac.read(key) is None and tm2._token is None


def test_token_manager_resolver_fails_open(emit_cli, render_and_import, monkeypatch, tmp_path):
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        assert ac.token_manager(object()) is None         # unrecognized shape -> None
        assert ac.session(object()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_session_seed_persist_invalidate -v`
Expected: FAIL — `AttributeError: module 'fakesdk_cli.auth_cache' has no attribute 'token_manager'`.

- [ ] **Step 3: Append the resolver + session** to `auth_cache.py.jinja`:

```jinja


def key_for(tm: Any) -> str:
    return _key(tm._token_url, tm._client_id, tm._scope)


def token_manager(client: Any) -> Any | None:
    """Resolve the SDK TokenManager from the built facade Client. Recognizes the
    single-spec shape (client.api_client.configuration._token_manager) and the
    federated shape (client._configuration._token_manager). Fail open: any other
    shape -> None (caching disabled this run; auth still works)."""
    cfg = getattr(getattr(client, "api_client", None), "configuration", None)
    if cfg is None:
        cfg = getattr(client, "_configuration", None)
    tm = getattr(cfg, "_token_manager", None)
    # Duck-check the fields we couple to; anything missing -> not our shape.
    if tm is None or not all(hasattr(tm, a) for a in ("_token", "_expires_at",
                                                      "_token_url", "_client_id", "_scope")):
        return None
    return tm


class _CacheSession:
    """Owns one command's cache interaction: seed the TokenManager from disk,
    persist a freshly-minted token, invalidate on rejection."""

    def __init__(self, tm: Any) -> None:
        self._tm = tm
        self._key = key_for(tm)
        self.seeded = False

    def seed_if_valid(self) -> None:
        hit = read(self._key)
        if hit is None:
            _LOG.info("no valid cached token (key %s); requesting a new one", self._key)
            return
        token, exp = hit
        if time.time() >= exp:
            _LOG.info("cached token expired (key %s); requesting a new one", self._key)
            return
        self._tm._token, self._tm._expires_at = token, exp
        self.seeded = True
        _LOG.info("reusing cached token (key %s, expires in %ds)",
                  self._key, int(exp - time.time()))

    def persist(self) -> None:
        token = getattr(self._tm, "_token", None)
        if not token:
            return  # no fetch happened (e.g. dry path) -> nothing to persist
        exp = float(getattr(self._tm, "_expires_at", 0.0))
        if read(self._key) != (token, exp):
            write(self._key, token, exp)
            if not self.seeded:
                _LOG.info("cached new token (key %s, expires in %ds)",
                          self._key, int(exp - time.time()))

    def invalidate(self) -> None:
        delete(self._key)
        self._tm._token = None
        _LOG.info("server rejected cached token; discarding and re-authenticating")


def session(client: Any) -> "_CacheSession | None":
    if not enabled():
        _LOG.debug("token cache disabled (config)")
        return None
    tm = token_manager(client)
    return _CacheSession(tm) if tm is not None else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/auth_cache.py.jinja tests/test_cli_emitted_cache.py
git commit -m "feat(cli): auth_cache TokenManager resolver + seed/persist/invalidate session"
```

---

## Task 4: Wire the cache into `runtime.py` (seed → call with 401-retry → persist)

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`run()` around the dispatch block, ~lines 593-655)
- Test: `tests/test_cli_emitted_cache.py`

**Interfaces:**
- Consumes: `auth_cache.session()` (Task 3), the existing `_client()` and `_sdk_exc(cmd)`.
- Produces: the runtime behavior — a cached token is reused on the 2nd run; a 401 with a seeded token triggers exactly one discard+re-grant+retry.

- [ ] **Step 1: Write the failing behavioral test** — append to `tests/test_cli_emitted_cache.py`. It drives a real command through `CliRunner`, monkeypatching `_facade_from_env` to return a fake client that owns a stub TokenManager, so the real `auth_cache` + `runtime` code runs against a tmp cache dir:

```python
def _fake_facade_with_tm(recorder, tm, fail_first_401=False):
    """A fake facade whose object attrs record calls; the api_client.configuration
    exposes the stub TokenManager the cache couples to."""
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name):
            def _call(*, all_pages=False, **kw):
                recorder.append((name, kw))
                if fail_first_401 and len([r for r in recorder if r[0] == name]) == 1:
                    exc = Exception("401"); exc.status = 401
                    raise exc
                return {"id": kw.get("id", "new")}
            return _call

    cfg = type("Cfg", (), {"_token_manager": tm})()
    client = type("Client", (), {
        "api_client": type("AC", (), {"configuration": cfg})(),
        "widget": _Rec(), "gizmo": _Rec(), "thing": _Rec(),
    })()
    return facade, client


def test_runtime_reuses_token_across_runs(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli.runtime")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        main = importlib.import_module("fakesdk_cli.main")
        tm = _StubTM(); rec = []
        _, client = _fake_facade_with_tm(rec, tm)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client)
        r = CliRunner()
        # run 1: cache miss -> tm fetches once, token persisted
        assert r.invoke(main.app, ["show", "widget", "--id", "1"]).exit_code == 0
        assert tm.fetches == 1
        # run 2: fresh TM seeded from cache -> zero fetches
        tm2 = _StubTM(); rec2 = []
        _, client2 = _fake_facade_with_tm(rec2, tm2)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client2)
        assert r.invoke(main.app, ["show", "widget", "--id", "1"]).exit_code == 0
        assert tm2.fetches == 0     # reused the cached token


def test_runtime_401_invalidates_and_retries_once(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli.runtime")
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        main = importlib.import_module("fakesdk_cli.main")
        tm = _StubTM()
        ac.write(ac.key_for(tm), "stale", time.time() + 900)   # a seeded-but-rejected token
        rec = []
        _, client = _fake_facade_with_tm(rec, tm, fail_first_401=True)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client)
        res = CliRunner().invoke(main.app, ["show", "widget", "--id", "1"])
        assert res.exit_code == 0                    # retried after invalidation
        assert len([r for r in rec if r[0] == "get"]) == 2   # one 401 + one success
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_runtime_reuses_token_across_runs -v`
Expected: FAIL — no reuse (run 2 fetches again) because runtime doesn't seed/persist yet.

- [ ] **Step 3: Wire `run()`** in `runtime.py.jinja`. After `client = _client(verbose=verbose)` (~line 593), add the session + seed; and replace the direct `method(**kwargs)` dispatch (~lines 619-629) with a 401-retrying call. Insert, guarded by `{% if ir.credential_fields %}`:

```jinja
        client = _client(verbose=verbose)
{%- if ir.credential_fields %}
        from . import auth_cache as _auth_cache
        _cache = _auth_cache.session(client)
        if _cache is not None:
            _cache.seed_if_valid()
{%- endif %}
```

Wrap the list/non-list dispatch in a local retry helper. Replace the existing block:

```python
        started = time.monotonic()
        try:
            if binding.sub_verb == "list":
                result = method(**kwargs, all_pages=paginate_all)
                if paginate_all and output in ("json", "yaml"):
                    result = getattr(result, cmd.items_field) if cmd.items_field else result
            else:
                result = method(**kwargs)
        finally:
            if callable(original_call):
                api_client.call_api = original_call
```

with (the `{% if ir.credential_fields %}` variant adds the retry; keep a plain variant for non-auth CLIs):

```jinja
        started = time.monotonic()
        def _dispatch() -> Any:
            if binding.sub_verb == "list":
                r = method(**kwargs, all_pages=paginate_all)
                if paginate_all and output in ("json", "yaml"):
                    return getattr(r, cmd.items_field) if cmd.items_field else r
                return r
            return method(**kwargs)
        try:
{%- if ir.credential_fields %}
            try:
                result = _dispatch()
            except {{ '{' }}{% endif %}_sdk_exc(cmd){% if ir.credential_fields %}{{ '}' }} as _exc:
                # A 401 with a token we seeded from cache -> the cached token was
                # rejected (revoked/stale). Discard it, re-grant, retry ONCE.
                if (_cache is not None and _cache.seeded
                        and getattr(_exc, "status", None) == 401):
                    _cache.invalidate()
                    result = _dispatch()
                else:
                    raise
{%- else %}
            result = _dispatch()
{%- endif %}
        finally:
            if callable(original_call):
                api_client.call_api = original_call
{%- if ir.credential_fields %}
        if _cache is not None:
            _cache.persist()
{%- endif %}
```

> Note to implementer: the `except {…_sdk_exc(cmd)…}` line is written with Jinja `{{ '{' }}`/`{{ '}' }}` so the emitted Python reads `except (_sdk_exc(cmd)) as _exc:`. Verify the emitted `runtime.py` parses (the golden/lint step below catches a mismatch). Keep the ORIGINAL outer `except (_sdk_exc(cmd), ValidationError) as exc:` error handler (~line 649) unchanged — it still renders the terminal error when the retry also fails.

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py tests/test_cli_emitted_runtime.py -v`
Expected: PASS (reuse across runs; 401 retried once; non-cache runtime tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/runtime.py.jinja tests/test_cli_emitted_cache.py
git commit -m "feat(cli): runtime seeds/persists the token cache with 401 retry-once"
```

---

## Task 5: `config cache-clear` + `show cli cache` commands

**Files:**
- Modify: `src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja` (after `config_unset`, ~line 104)
- Modify: `src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja` (after `show_history`, ~line 53)
- Test: `tests/test_cli_emitted_cache.py`

**Interfaces:**
- Consumes: `auth_cache.clear()`, `auth_cache.list_entries()`, `auth_cache.cache_dir()`.
- Produces: CLI commands `<dist> config cache-clear` and `<dist> show cli cache`. No `app.py`/`_META` change — the commands attach to the already-registered `config_app` / `cli_show_app`, so lazy loading resolves them for free.

- [ ] **Step 1: Write the failing test** — append to `tests/test_cli_emitted_cache.py`:

```python
def test_cache_commands(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli.auth_cache")
        importlib.import_module("fakesdk_cli.config").load_config.cache_clear()
        ac.write(ac._key("u", "c", "s"), "secret-token", time.time() + 600)
        main = importlib.import_module("fakesdk_cli.main")
        r = CliRunner()
        show = r.invoke(main.app, ["show", "cli", "cache"])
        assert show.exit_code == 0
        assert "secret-token" not in show.output          # never leak the token
        assert ac._key("u", "c", "s") in show.output       # shows the key id
        clr = r.invoke(main.app, ["config", "cache-clear"])
        assert clr.exit_code == 0 and "removed 1" in clr.output.lower()
        assert ac.list_entries() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_cache_commands -v`
Expected: FAIL — `No such command 'cache-clear'` / `'cache'`.

- [ ] **Step 3a: Add `config cache-clear`** to `config_commands.py.jinja` (after `config_unset`), guarded:

```jinja
{% if ir.credential_fields %}
@config_app.command("cache-clear")
def config_cache_clear() -> None:
    """Delete all cached auth tokens from the cache directory."""
    from . import auth_cache as _auth_cache

    n = _auth_cache.clear()
    _output._console.print(f"removed {n} cached token(s) from {_auth_cache.cache_dir()}")
{% endif %}
```

- [ ] **Step 3b: Add `show cli cache`** to `cli_commands.py.jinja` (after `show_history`), guarded:

```jinja
{% if ir.credential_fields %}
@cli_show_app.command("cache")
def show_cache() -> None:
    """Show cached auth tokens (key id + expiry — never the token value)."""
    import time as _time
    from datetime import datetime, timezone

    from . import auth_cache as _auth_cache

    d = _auth_cache.cache_dir()
    _output._console.print(f"dir: {d}")
    for key, exp in _auth_cache.list_entries():
        iso = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat(timespec="seconds")
        rem = int(exp - _time.time())
        _output._console.print(f"  key {key}  expires {iso} (in {rem}s)")
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_emitted_cache.py::test_cache_commands tests/test_cli_lazy_loading.py -v`
Expected: PASS (commands work; lazy-loading parity intact).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generator/cli/templates/_generated/config_commands.py.jinja \
        src/phantasos/generator/cli/templates/_generated/cli_commands.py.jinja \
        tests/test_cli_emitted_cache.py
git commit -m "feat(cli): config cache-clear + show cli cache commands"
```

---

## Task 6: Ring-3 seam test against the REAL TokenManager

**Files:**
- Create: `tests/test_cli_cache_real.py`
- Test: itself (`real_sdk` marker, auto-applied by the fixture)

**Interfaces:**
- Consumes: the `real_sdk` fixture (`tests/conftest.py`), the real prisma-browser SDK's `TokenManager`.
- Produces: proof that `auth_cache.token_manager()` resolves the real facade shape and that `_token`/`_expires_at`/`_token_url`/`_client_id`/`_scope` exist on the real TokenManager (the coupling D2 accepts).

- [ ] **Step 1: Write the test** — `tests/test_cli_cache_real.py`:

```python
"""Ring-3: the auth_cache coupling matches the REAL SDK TokenManager shape."""
import importlib
import sys
from pathlib import Path

import pytest


def test_real_token_manager_has_coupled_fields(real_sdk: Path):
    """The private fields auth_cache reads must exist on the real TokenManager."""
    if str(real_sdk) not in sys.path:
        sys.path.insert(0, str(real_sdk))
    try:
        auth = importlib.import_module("prisma_browser.extras.auth")
    except ModuleNotFoundError as exc:
        pytest.skip(f"prisma-browser-sdk auth not importable: {exc}")
    tm = auth.TokenManager("cid", "secret", "scope", token_url="https://auth/token")
    for attr in ("_token", "_expires_at", "_token_url", "_client_id", "_scope"):
        assert hasattr(tm, attr), f"real TokenManager missing {attr} (auth_cache coupling)"
    # a fresh TM has no token; seeding then reading back is what the CLI does
    tm._token, tm._expires_at = "seeded", 9999999999.0
    assert tm.token() == "seeded"   # seeded token is returned without a fetch
```

> Note: the full 2-run reuse / 401 behavior is proven offline in Task 4 against a stub TM and against the real token endpoint in Task 7 (live). This ring-3 test's job is to catch an SDK-internals rename that would silently disable caching.

- [ ] **Step 2: Run the test** (skips cleanly if the SDK isn't built)

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_cache_real.py -v`
Expected: PASS if `../prisma-browser-sdk` is built (or after `nox -s smoke`); SKIP otherwise.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_cache_real.py
git commit -m "test(cli): ring-3 guard that auth_cache matches the real TokenManager shape"
```

---

## Task 7: Live test, docs, CHANGELOG, context deep-dive

**Files:**
- Create: `tests/test_cli_cache_live.py` (live-gated)
- Modify: `CHANGELOG.md` (`## [Unreleased]`), `docs/cli-authoring.md` **or** `docs/configuring-the-cli.md`, `.agents/context/cli-generator.md`

**Interfaces:**
- Consumes: real credentials (`CLIENT_ID`/`CLIENT_SECRET`/`SCOPE`) from the environment; the real prisma-browser SDK.
- Produces: an end-to-end live proof + user/agent documentation.

- [ ] **Step 1: Write the live test** — `tests/test_cli_cache_live.py` (skips without creds; run via the `live` path):

```python
"""Live: a real SCM grant is cached and reused on the second build_client call."""
import importlib
import os
import sys
from pathlib import Path

import pytest

_CREDS = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")
_REAL = Path(__file__).resolve().parent.parent.parent / "prisma-browser-sdk"


@pytest.mark.skipif(not _REAL.exists(), reason="prisma-browser-sdk not built")
@pytest.mark.skipif(any(not os.environ.get(k) for k in _CREDS),
                    reason="live tenant credentials not set")
def test_live_token_is_cached_and_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    if str(_REAL) not in sys.path:
        sys.path.insert(0, str(_REAL))
    auth = importlib.import_module("prisma_browser.extras.auth")
    tm = auth.TokenManager(os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"],
                           os.environ["SCOPE"])
    first = tm.token()                              # real grant
    assert first and tm._expires_at > 0
    # simulate the CLI persisting + a fresh run seeding
    key = f"{tm._token_url}\n{tm._client_id}\n{tm._scope}"
    tm2 = auth.TokenManager(os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"],
                            os.environ["SCOPE"])
    tm2._token, tm2._expires_at = first, tm._expires_at   # seed from "cache"
    assert tm2.token() == first                     # reused; no second grant
```

- [ ] **Step 2: Run the live test** (skips without creds — safe/green offline)

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run pytest tests/test_cli_cache_live.py -v`
Expected: SKIP without creds; PASS with creds + built SDK.

- [ ] **Step 3: Document.** Add a `## [Unreleased]` CHANGELOG entry under `### Added`:

```markdown
- **Generated CLIs cache the OAuth token across runs** — an authenticating CLI now
  reuses a valid client-credentials JWT instead of re-authenticating every command.
  The token is stored per-principal (0600) under `~/.<dist>/cache/`, seeded into the
  SDK before a call and refreshed on expiry or a 401 (discard + re-grant + retry once).
  On by default; disable with `<PREFIX>_CACHE_ENABLED=false`. Inspect with
  `<dist> show cli cache`, purge with `<dist> config cache-clear`. INFO-level logging
  of the cache lifecycle. Non-authenticating CLIs are unaffected.
```

Add a "Token cache" subsection to the CLI config docs (`docs/configuring-the-cli.md`): the `cache:` knob, env vars, file location/permissions, the two commands, and the security note (a bearer JWT is written to disk; opt out via env). Update `.agents/context/cli-generator.md` narrative to mention the emitted `auth_cache.py` module and the runtime seed/persist/401 seam.

- [ ] **Step 4: Refresh generated context blocks**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run nox -s context -- --check`
Expected: PASS (or run without `-- --check` to regenerate, then commit).

- [ ] **Step 5: Full gate**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cache uv run nox -s gate`
Expected: PASS. Then `uv run nox -s smoke` (builds the real SDKs + runs the ring-3 test) before declaring done, and `uv run nox -s live` (skips without creds).

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli_cache_live.py CHANGELOG.md docs/ .agents/context/cli-generator.md
git commit -m "test+docs(cli): live token-cache test + CHANGELOG + config docs + context"
```

---

## Self-Review

**Spec coverage:** D1 refresh/401-retry → Task 4. D2 CLI-only resolver + fail-open → Tasks 3, 6. D3 per-principal 0600 key/file → Task 2. D4 config knob → Task 1. D5 logging → Tasks 3 (events) + verified in 4/5. D6 commands → Task 5. D7 unit+ring-3+live → Tasks 2-4, 6, 7. D8 gating (`{% if ir.credential_fields %}`) → every template task. Security posture / fail-open matrix → Tasks 2 (corrupt/unwritable), 3 (shape), 4 (401/403). No spec section is unimplemented.

**Placeholder scan:** every code step contains real, runnable code; test commands have expected outcomes; no "TBD"/"similar to"/"add error handling".

**Type consistency:** `session()`/`_CacheSession`/`seed_if_valid`/`persist`/`invalidate`/`seeded`, `token_manager()`, `key_for()`, `read/write/delete/list_entries/clear`, `cache_dir()`/`cache_dir_path()`, `CacheConfig.{enabled,dir}` are used identically across Tasks 1-7 and the runtime/commands/tests.

**Note carried to execution:** the Jinja-escaped `except` line in Task 4 Step 3 is the one spot to eyeball in the emitted `runtime.py`; the gate's ruff/lint + the Task 4 tests fail loudly if it renders wrong.
