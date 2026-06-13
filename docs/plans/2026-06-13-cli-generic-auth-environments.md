# Generic Auth-Component-Driven Environments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Named auth environments in a generated CLI, with the environment's field set derived generically from the product's auth component — no SCM/client-credentials shape baked into the generator.

**Architecture:** A `credential_fields()` contract on an `AuthComponent` base, carried into the CLI on the **typed `CliIR`** (not a stringly-typed emitted constant). Environments live in `config.yml` as an **isolated passthrough key** with their own resolver (kept off the static-schema validation machinery). The `config environment` command group is a **hand-written runtime module** driven by `ir.credential_fields`, not Jinja-generated per field. Genericity is proven by a **stub-component test**, deferring any real second auth scheme until a product needs it.

**Tech Stack:** Python 3.12, Pydantic v2, Jinja2 (`StrictUndefined`), Typer, pytest. Tracks GH #18.

---

## Decisions log (grill-me + two expert reviews, 2026-06-13)

- **Scope:** environments are auth-only; fields derive from the auth component's `credential_fields()`.
- **Auth refactor:** `AuthComponent(_Component)` base with an **enforced** `credential_fields()` (enforced via `__init_subclass__` raising `TypeError` — **not** `assert`, which `python -O` strips — plus a registration test). Rename `oauth_client_credentials` → `scm_oauth` (`OAuthClientCredentials` → `ScmOAuth`), bake the Strata `token_url` default, full hard cut.
- **Descriptor location (S4):** `credential_fields` rides the **typed `CliIR`** (emitted as `spec.py` + `ir.json`, re-validated at runtime), removing the list-of-dicts constant and its manual key-match test.
- **Environments storage:** an **isolated top-level `environments:` key** in `config.yml`, validated/read by a dedicated `resolve_environment()` — kept OUT of the static `ConfigFile` tree (`_validate`/`_del_path`/`_collect_extras`/`effective_dict`), which assumes a fixed shallow schema.
- **Command group:** **hand-written** runtime module (copied like `spec.py`), building its Typer options from `ir.credential_fields` — keeps secret/prompt/redaction logic out of generated Jinja.
- **Selection (`-e`):** per-command `--environment/-e` in the `Common` panel (UX-review placement) that sets a `contextvars.ContextVar` — NOT an `os.environ` stash. Precedence: flag-contextvar > `{PREFIX}_ENVIRONMENT` > `default_environment`.
- **Precedence (M2/M3):** presence-based resolution (`x if x is not None else y`, not `or`) in both the runtime and the SDK `api_client_from_env` (`_pick`).
- **2nd auth scheme (Cortex XDR):** **deferred.** Genericity proven by a stub `AuthComponent` test. Ship a real scheme when a product spec lands.
- **Execution:** staged into 4 independently reviewable PRs (below), not one bundle.

---

## ⮕ Feasibility verdict: out of the box?

**No — needs bounded wiring; no redesign.** Verified enablers: pluggable component registry (`config.py:68`, `productconfig.py:179`); generic `Client.from_env(**kwargs)` passthrough (`client.py.jinja:35-37`); Jinja-rendered per-product config (`render_cli.py:350`); the runtime already loads a typed IR from `ir.json` (`runtime.py.jinja:27-30`, emitted at `render_cli.py:358-362`) — the rail S4 rides. The one real gap: `render_cli`'s context is `{ir, package, env_prefix, distribution}` (`render_cli.py:336-341`) and `loaded.auth` (`cli.py:111`) is never threaded in — so the descriptor must reach the IR at emit time.

---

## File Structure

**Rename (full hard cut, PR1):**
- `src/phantasos/generator/sdk/components/auth/oauth_client_credentials.py.jinja` → `auth/scm_oauth.py.jinja`.
- `products/adem/sdk.yml`, `products/prisma-browser/sdk.yml` — `type: scm_oauth`, drop the now-default `token_url`.
- `src/phantasos/__init__.py`; `tests/{test_config,test_framework,test_productconfig}.py`; docs `ARCHITECTURE.md`, `AUTHORING_A_SPEC.md`, `ONBOARDING.md`.

**Create:**
- `src/phantasos/generator/cli/templates/_generated/environment_commands.py` — **hand-written, copied verbatim** (like `spec.py`) into the emitted package; the `config environment create|activate|list|current` group, driven at runtime by `ir.credential_fields`. Holds the single `_redact()` helper.
- `tests/test_generic_auth_environments.py` — descriptor + enforcement + stub-genericity tests.

**Modify:**
- `src/phantasos/config.py` — `AuthComponent` base (`__init_subclass__` raise-enforcement); rename `OAuthClientCredentials` → `ScmOAuth(AuthComponent)` declaring `credential_fields()`, with baked `token_url`; `BUILTIN_AUTH = {"scm_oauth": ScmOAuth}`. Imports `CredentialField` from the IR module (see Task 2 note).
- `src/phantasos/generator/cli/ir.py` — define `CredentialField`; add `credential_fields: list[CredentialField] = []` to `CliIR`. (This module is copied verbatim to the emitted `spec.py`, so `CredentialField` must live here to remain importable at runtime.)
- `src/phantasos/generator/cli/render_cli.py` + `cli.py` — thread `auth=loaded.auth`; populate `ir.credential_fields` from `auth.credential_fields()` before emitting `ir.json`.
- `src/phantasos/generator/cli/templates/_generated/config.py.jinja` — passthrough `environments` (NOT in `ConfigFile`): `resolve_environment(name)` (reads the raw `environments:` mapping, validates against `ir.credential_fields`, resolves `${VAR}`); leave `_validate`/`effective_dict` untouched.
- `src/phantasos/generator/cli/templates/_generated/runtime.py.jinja` (`_client()`) — contextvar selection + presence-based `from_env(**overrides)`.
- `src/phantasos/generator/cli/templates/_generated/commands.py.jinja` — `--environment/-e` (`Common` panel) that sets the selection contextvar.
- `src/phantasos/generator/cli/templates/_generated/app.py.jinja` — register the env group on `config_app` (gated on `ir.credential_fields`).
- `src/phantasos/generator/cli/templates/_generated/default_config.yml.jinja` — commented `environments:` example, guarded by `{% if credential_fields %}`.
- `src/phantasos/generator/cli/scaffold_context.py:19-31` — `_auth_env_vars` derives from `credential_fields`.

---

## PR1 / Task 1: Holistic auth refactor — `AuthComponent` base + enforced contract + rename

**Files:** Modify `src/phantasos/config.py`, `src/phantasos/__init__.py`, `products/{adem,prisma-browser}/sdk.yml`, `tests/{test_config,test_productconfig,test_framework}.py`, docs; Rename `auth/oauth_client_credentials.py.jinja` → `auth/scm_oauth.py.jinja`; Test `tests/test_generic_auth_environments.py`.

- [ ] **Step 1: Failing tests** (registration + baked default + enforcement)

```python
import pytest
from phantasos.config import ScmOAuth, AuthComponent, BUILTIN_AUTH
from phantasos.generator.cli.ir import CredentialField

def test_scm_oauth_registered_and_bakes_token_url():
    assert BUILTIN_AUTH["scm_oauth"] is ScmOAuth
    assert ScmOAuth(type="scm_oauth").token_url == \
        "https://auth.apps.paloaltonetworks.com/oauth2/access_token"

@pytest.mark.parametrize("model", BUILTIN_AUTH.values())
def test_every_auth_component_declares_credential_fields(model):
    fields = model(type=model.model_fields["type"].default or "x").credential_fields()
    assert fields and all(isinstance(f, CredentialField) for f in fields)

def test_contract_enforced_at_definition():
    with pytest.raises(TypeError, match="must override credential_fields"):
        class BadAuth(AuthComponent):
            pass
```

- [ ] **Step 2: Run → fail** (`ImportError: ScmOAuth`).

- [ ] **Step 3: Implement** in `config.py`

```python
from phantasos.generator.cli.ir import CredentialField   # self-contained module; see Task 2 note

class AuthComponent(_Component):
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if cls.credential_fields is AuthComponent.credential_fields:   # resolved-attr, not __dict__
            raise TypeError(f"{cls.__name__} must override credential_fields()")  # raise, not assert (-O safe)
    def credential_fields(self) -> list[CredentialField]:
        raise NotImplementedError

class ScmOAuth(AuthComponent):
    """Strata Cloud (SCM/SASE) OAuth2 client-credentials provider."""
    token_url: str = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
    scope_env: str = "SCOPE"
    client_id_env: str = "CLIENT_ID"
    client_secret_env: str = "CLIENT_SECRET"  # noqa: S105
    base_url_env: str = "BASE_URL"
    config_class_name: str = "SdkConfiguration"
    template: str = "auth/scm_oauth.py.jinja"
    def credential_fields(self) -> list[CredentialField]:
        return [
            CredentialField(name="client_id", env_var=self.client_id_env),
            CredentialField(name="client_secret", env_var=self.client_secret_env, secret=True),
            CredentialField(name="scope", env_var=self.scope_env),
            CredentialField(name="base_url", env_var=self.base_url_env, client_kwarg="host"),
        ]

BUILTIN_AUTH = {"scm_oauth": ScmOAuth}
```

(`CredentialField` is defined in Task 2; do Task 2 Step 3's `CredentialField` definition first, or stub it, since `config.py` imports it.)

- [ ] **Step 4: `git mv` the template + ripple the rename**

```bash
git mv src/phantasos/generator/sdk/components/auth/oauth_client_credentials.py.jinja \
       src/phantasos/generator/sdk/components/auth/scm_oauth.py.jinja
```
Update `__init__.py` (`ScmOAuth`), both product `sdk.yml`s (`type: scm_oauth`, delete `token_url:`), the three test files, and the three docs.

- [ ] **Step 5: Resolve M3 — presence-based `_pick` in `scm_oauth.py.jinja`**

```jinja
def _pick(overrides, key, env_var):
    v = overrides.pop(key, None)
    return v if v is not None else os.environ.get(env_var)

def api_client_from_env(**overrides) -> ApiClient:
    client_id = _pick(overrides, "client_id", "{{ client_id_env }}")
    client_secret = _pick(overrides, "client_secret", "{{ client_secret_env }}")
    scope = _pick(overrides, "scope", "{{ scope_env }}")
    host = _pick(overrides, "host", "{{ base_url_env }}") or DEFAULT_BASE_URL
    ...  # missing-check + return unchanged
```
Identical behavior for non-empty values, so `test_framework.py` (renders this template) stays green.

- [ ] **Step 6: Run → green** (`pytest tests/test_generic_auth_environments.py tests/test_config.py tests/test_productconfig.py tests/test_framework.py -q`; `git grep -n oauth_client_credentials src/ tests/ products/` → empty). **Commit.** This PR is a pure refactor — no behavior change.

## PR2 / Task 2: `CredentialField` on the typed IR + thread auth into emission + stub-genericity proof

**Files:** Modify `src/phantasos/generator/cli/ir.py`, `render_cli.py`, `cli.py`; Test `tests/test_generic_auth_environments.py`.

> **Note (CredentialField home):** `ir.py` is copied verbatim to the emitted `spec.py` (`render_cli.py:359-360`) and re-validated at runtime, so it must stay self-contained (pydantic + stdlib only). `CredentialField` therefore lives in `ir.py`; `config.py` imports it from there (an SDK→CLI-module import — acceptable because `ir.py` is a dependency-free leaf). If that import direction is undesirable, the fallback is a 5-line `phantasos/_credential.py` copied into the emitted package alongside `spec.py`; default to the `ir.py` home.

- [ ] **Step 1: Failing test** (a stub auth component drives the emitted descriptor — this is the genericity proof, no real 2nd scheme)

```python
def test_arbitrary_auth_component_drives_credential_fields(tmp_path):
    from phantasos.config import AuthComponent
    from phantasos.generator.cli.ir import CredentialField
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.introspect import introspect
    from phantasos.generator.cli.render_cli import render_cli
    from tests.conftest import FAKESDK_FIXTURE, FAKESDK_CLI_CONFIG

    class StubAuth(AuthComponent):                      # NOT client-credentials shaped
        type: str = "stub"
        def credential_fields(self):
            return [CredentialField(name="api_key_id", env_var="API_KEY_ID"),
                    CredentialField(name="api_key", env_var="API_KEY", secret=True),
                    CredentialField(name="base_url", env_var="BASE_URL", client_kwarg="host")]

    ir = build_cli_ir(introspect("fakesdk", FAKESDK_FIXTURE), FAKESDK_CLI_CONFIG)[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK", auth=StubAuth())
    import json
    emitted = json.loads((tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text())
    names = [f["name"] for f in emitted["credential_fields"]]
    assert names == ["api_key_id", "api_key", "base_url"]   # generic; no client_id bleed-through
```

- [ ] **Step 2: Run → fail** (`render_cli` has no `auth` kwarg; `CliIR` has no `credential_fields`).

- [ ] **Step 3: Implement** — define `CredentialField` in `ir.py` and add the field to `CliIR`:

```python
class CredentialField(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    env_var: str
    secret: bool = False
    required: bool = True
    client_kwarg: str | None = None

class CliIR(BaseModel):
    ...
    credential_fields: list[CredentialField] = []
```
Thread it through emission: `render_cli(..., auth=None)`; when `auth` has `credential_fields`, set `ir = ir.model_copy(update={"credential_fields": auth.credential_fields()})` before the `ir.model_dump_json()` write (`render_cli.py:362`). In `cli.py`, pass `auth=loaded.auth`.

- [ ] **Step 4: Run → green. Commit.**

## PR3 / Task 3: Emitted environments (isolated key) + runtime resolution + `-e`

**Files:** Modify `config.py.jinja`, `runtime.py.jinja`, `commands.py.jinja`, `app.py.jinja`, `default_config.yml.jinja`; Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing tests** (isolated-key resolution; env-wins; `${VAR}`; contextvar precedence). Use an `emitted_auth` fixture that renders with `auth=ScmOAuth(...)`.

```python
def test_resolve_environment_envref_and_env_wins(emitted_auth, monkeypatch, tmp_path):
    home = tmp_path / "home"; (home / ".fakesdk").mkdir(parents=True)
    (home / ".fakesdk" / "config.yml").write_text(
        "configuration: {output: {format: json}}\n"
        "environments:\n  prod:\n    client_id: ENVID\n    client_secret: ${PROD_SECRET}\n"
        "    scope: tsg_id:1\n    base_url: https://env\n")
    monkeypatch.setenv("HOME", str(home)); monkeypatch.setenv("PROD_SECRET", "s3cr3t")
    monkeypatch.setenv("CLIENT_ID", "SHELLID")            # ambient var must WIN
    import importlib
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    captured = {}
    monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: captured.update(kw) or object())
    rt._client()
    assert captured["client_id"] == "SHELLID"             # env-wins (presence)
    assert captured["client_secret"] == "s3cr3t"          # ${PROD_SECRET}
    assert captured["host"] == "https://env"              # base_url -> host
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement isolated-key resolution in `config.py.jinja`** (do NOT touch `ConfigFile`/`_validate`/`effective_dict`):

```python
import re as _re
_ENVREF = _re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_CRED = {{ credential_fields | tojson }}            # name/env_var/secret/client_kwarg, from ir at emit
def _raw_environments() -> dict:
    path = config_path()
    if not path.exists(): return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data.get("environments", {}) if isinstance(data, dict) else {}
def default_environment() -> str | None:
    return _raw_environments().get("__default__")       # or a sibling 'default_environment:' key
def _resolve_value(v):
    if isinstance(v, str):
        m = _ENVREF.match(v)
        if m: return os.environ.get(m.group(1))
    return v
def resolve_environment(name: str) -> dict:
    env = _raw_environments().get(name) or {}
    out = {}
    for f in _CRED:                                     # validate against the descriptor
        out[f["name"]] = _resolve_value(env.get(f["name"]))
    return out
```

> Note: the descriptor is available to `config.py.jinja` at emit (Task 2 passes `credential_fields` into the render `ctx`); the runtime ALSO has it typed via `_ir().credential_fields`. Use the IR copy in `runtime.py` (Step 4); `config.py`'s `_CRED` constant is only for `resolve_environment`/redaction and may instead import from `spec`.

- [ ] **Step 4: Implement `_client()` (contextvar selection + presence-based)** in `runtime.py.jinja`:

```python
import contextvars, os as _os
_SELECTED = contextvars.ContextVar("selected_env", default=None)
def select_environment(name): _SELECTED.set(name)      # set by the -e option (commands.py.jinja)
def _selected_environment():
    return _SELECTED.get() or _os.environ.get("{{ env_prefix }}_ENVIRONMENT") or _config.default_environment()
def _facade_from_env(**kw):
    return importlib.import_module(_ir().facade_module).Client.from_env(**kw)
def _client():
    ...  # dotenv load
{% raw %}    name = _selected_environment()
    env = _config.resolve_environment(name) if name else {}
    overrides = {}
    for f in _ir().credential_fields:
        ev = _os.environ.get(f.env_var)                 # presence, not truthiness
        val = ev if ev is not None else env.get(f.name)
        if val is not None:
            overrides[f.client_kwarg or f.name] = val
    return _facade_from_env(**overrides){% endraw %}
```
Add `--environment/-e` to `commands.py.jinja`'s `Common`-panel block calling `_rt.select_environment(environment)` at entry. Gate the whole block on `{% if credential_fields %}`; with no auth, `_client()` falls back to `_facade_from_env()` (today's behavior — existing `emitted` tests unaffected).

- [ ] **Step 5: Run → green. Commit.**

## PR4 / Task 4: Hand-written `config environment` command group

**Files:** Create `environment_commands.py` (copied verbatim into the emitted package via a new entry in `render_cli`'s copy list, like `spec.py`); Modify `app.py.jinja`/`config_commands.py.jinja` to register it on `config_app` (gated on `ir.credential_fields`); Test `tests/test_cli_emitted.py`.

- [ ] **Step 1: Failing test** (create with hidden secret, auto-activate, list redacts, current, dup errors)

```python
def test_environment_group(emitted_auth, monkeypatch, tmp_path):
    home = tmp_path / "home"; monkeypatch.setenv("HOME", str(home))
    from typer.testing import CliRunner; import importlib
    app = importlib.import_module("fakesdk_cli._generated.app").build_generated_app()
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    r = CliRunner()
    out = r.invoke(app, ["config","environment","create","prod","--client-id","abc",
                         "--scope","tsg_id:1","--base-url","https://api"], input="s3cr3t\n")
    assert out.exit_code == 0
    assert "prod" in r.invoke(app, ["config","environment","current"]).stdout
    lst = r.invoke(app, ["config","environment","list"]).stdout
    assert "prod" in lst and "s3cr3t" not in lst                 # never prints secrets
    assert r.invoke(app, ["config","environment","create","prod"]).exit_code == 2  # dup → 2
```

- [ ] **Step 2: Run → fail** (no `environment` subcommand).

- [ ] **Step 3: Implement** `environment_commands.py` as a **hand-written** module (no per-field Jinja): build the `create` command's options dynamically from `_ir().credential_fields` (secret fields → `hide_input=True` prompt; missing → prompt), write under the isolated `environments:` key (auto-activate when no default), `--force` to overwrite (else exit 2). `list`/`current` read via `config.resolve_environment`/`_raw_environments`; both route printing through a single `_redact(value, field)` helper (`***` for `secret=True`, literal `${REF}` preserved). Add the gating test: a no-auth emitted CLI exposes no `environment` group and `ir.credential_fields == []`. Verify `create` does NOT record history (`_history_entry` logs `shlex.join(argv)`, `runtime.py.jinja:303`) — assert no secret in the history file.

- [ ] **Step 4: Run → green. Commit.**

## Deferred (post-prototype)

- Real second auth component (e.g. Cortex XDR) — when a product spec needs it; the stub test already proves the descriptor is generic.
- `${VAR}` partial interpolation (only full `^\$\{VAR\}$` is resolved); missing-ref diagnostics; dynamic shell completion for env names; `config show` surfacing environments (currently `config show` = static config only, which sidesteps secret-in-effective_dict entirely).
- `uv run nox -s gate` (offline) + `uv run nox -s live` before declaring a phase complete (CLAUDE.md).

## Self-review

- **Spec coverage (#18):** rename+contract (PR1), descriptor on IR + generic proof (PR2), isolated-key environments + resolution + `-e` (PR3), command group + redaction + gating + history-leak test (PR4). Cortex intentionally deferred.
- **Review items resolved:** M1 (`build_generated_app`), M2/M3 (presence-based + `_pick`), S1 (contextvar), S2 (resolved-attr enforcement), S4 (typed IR), H1/H2 (isolated key sidesteps the static-machinery hardening + the defaults-sync guard), the `-O` hole (`raise` not `assert`), secret-leak paths (single `_redact` + history assertion).
- **Type consistency:** `CredentialField(name, env_var, secret, required, client_kwarg)` defined once in `ir.py`, used by `config.py`, the IR, `resolve_environment`, and the runtime loop; `_facade_from_env`/`select_environment`/`resolve_environment`/`default_environment` defined in PR3 and used in PR3/PR4.
- **Open implementation note:** `CredentialField` home (ir.py vs a copied `_credential.py`) — default ir.py; revisit only if the import direction proves awkward.
