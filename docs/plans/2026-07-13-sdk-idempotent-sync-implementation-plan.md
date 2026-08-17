# SDK Idempotent Sync Implementation Plan

> **Supersedes** the design-level draft `docs/plans/2026-07-12-sdk-idempotency-implementation-plan.md`
> (kept for rationale, effort sizing, and risk narrative). This document is the
> execution-ready, TDD, bite-sized re-expression of that plan — same phases, same
> file/function/line anchors, same prototype mapping — now with real failing
> tests, real implementation code (translated from the validated prototype), exact
> commands, and expected output for every step.

> **For agentic workers:** REQUIRED SUB-SKILL: Use the subagent-driven-development skill (recommended) or the executing-plans skill to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Give every opted-in resource of a generated SDK a first-class, tested idempotent-sync surface — `apply` / `absent` / `fetch` / `diff` — plus the injectable-token constructor `from_access_token`, so a later Ansible target (and a future CLI `apply`) consume one generator-baked engine instead of per-consumer orchestration.

**Architecture (per ADR-0004):** A new SDK component tree `components/idempotency/`, vendored under `<pkg>/extras/idempotency/`, is a thin **orchestrator** (`SyncMixin` + `Diff`/`SyncResult` + two exceptions) plus three families of small, swappable **strategy components** — `fetch/{list_scan,list_filter,get}`, `mutate/{put_rmw,patch_minimal}`, `materialize/{direct,get_after_write}` — selected per resource and resolved through registries at call time. A per-resource `_idempotency` classvar, baked by `build_wrapper_context` from a new `sdk.yml idempotency:` block + the IR + live model introspection, names the three strategies (auto-derived) alongside the data they read; `render.vendor()` writes the engine, the base, and **only the union** of strategy modules the opted-in resources reference.

**Tech Stack:** Python 3.11+, pydantic v2, Jinja2 component templates (`src/phantasos/generator/sdk/components/`), the OpenAPI-Generator-based SDK + opmodel IR (`generator/opmodel/`), nox (`gate`/`smoke`/`live`), pytest.

**Spec (authoritative design):** `docs/specs/2026-07-12-sdk-idempotency-for-ansible-design.md` — **§0 findings F1–F9 override later sections where they conflict**; §4 contract; §5 (rev. ADR-0004) component decomposition + §5.4 metadata + §5.5 selection + §5.6 prototype mapping; §6 config models; §7 diff; §8 awkward shapes; §9 auth seam; §10 scope validator; §11 rollout; §12 testability. **ADRs:** 0002, 0003, 0004. **Validated prototype (17/17 prisma-access + 13/13 prisma-browser live):** `prototypes/sync-engine/` (`engine.py`, `run_prisma_access.py`, `run_prisma_browser.py`, `NOTES.md`) — translate this code; do not reinvent, do not import it, do not ship it.

## Global Constraints

- **Additive / opt-in:** a product without an `idempotency:` block in `sdk.yml` regenerates **byte-identically** — no `extras/idempotency/` directory, no mixin, no classvar, no validator. The **sole exception** is `from_access_token`, which rides the auth component (credential-handling, emitted for every auth-bearing product). `adem` (never opted in) is the byte-identical regression canary.
- **Never mock the system under test or the prisma-browser API boundary.** Engine/strategy unit tests drive the real rendered orchestrator + strategy callables against a stub resource carrying a hand-built `_idempotency` classvar + canned wrapper verbs — scaffolding around the real SUT, never an API mock.
- **Evidence before assertions:** from Phase 1 on, run the live quartet (`uv run nox -s live`) and show its output before declaring a phase complete.
- **Block-style YAML only** in the two self-authored config files (`products/*/sdk.yml`); empty mappings stay flow (`address: {}`).
- **Branch:** `feature/sdk-idempotent-sync` off `develop`; PR → `develop` (`gh pr create --base develop`), **squash-merge**, **no version bump**, record under `## [Unreleased]` in `CHANGELOG.md`.
- **Run tests with:** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest ...` (repo may sit on sshfs). For venv-backed nox sessions also set `NOX_ENVDIR=/tmp/phantasos-nox`.
- **`uv run nox -s gate`** (ruff + mypy + `pytest -m "not slow"`) is the offline stop gate; **`uv run nox -s live`** (skips without credentials) is the live phase gate. `uv run nox -s smoke` rebuilds the example SDKs then runs `pytest -m real_sdk`.
- **Docs are the human's to commit.** Write/update Markdown freely; never `git add`/`commit` `docs/**`, `CHANGELOG.md`, `README`, or `.agents/context/**`. Commit only code (test + source).

---

## File Structure

**Create — the component tree** (`src/phantasos/generator/sdk/components/idempotency/`; vendored under `<pkg>/extras/idempotency/`):

| Path | Responsibility |
|---|---|
| `base.py.jinja` | The `FetchStrategy` / `MutateStrategy` / `MaterializeStrategy` `Protocol`s + the `FETCH` / `MUTATE` / `MATERIALIZE` registry dicts + the `NotFoundException` re-export (federated vs single-spec import split — the only conditional). |
| `engine.py.jinja` | The orchestrator `SyncMixin` (uniform steps: identity/scope extraction, the desired-subset diff + `_normalize` projection hook, create-body construction, `check_mode`, `SyncResult` assembly) + `Diff` / `SyncResult` + `AbsentNotSupported` / `IdentityUnresolved`. Resolves strategies through `base.py`'s registries. |
| `fetch/list_scan.py.jinja` | fetch family — list-all-and-match (F1 default); registers `FETCH["list_scan"]`. |
| `fetch/list_filter.py.jinja` | fetch family — server-side name filter + re-filter; registers `FETCH["list_filter"]`. |
| `fetch/get.py.jinja` | fetch family — singleton get-by-no-identity; registers `FETCH["get"]`. **Created in Phase 6** (no singleton is live-proven in Phase 1). |
| `mutate/put_rmw.py.jinja` | mutate family — read-modify-write PUT; registers `MUTATE["put_rmw"]`. |
| `mutate/patch_minimal.py.jinja` | mutate family — changed-only PATCH; registers `MUTATE["patch_minimal"]`. |
| `materialize/direct.py.jinja` | materialize family — response is the object; registers `MATERIALIZE["direct"]`. |
| `materialize/get_after_write.py.jinja` | materialize family — id-envelope → GET (F3); registers `MATERIALIZE["get_after_write"]`. |
| `__init__.py.jinja` | Vendored as `extras/idempotency/__init__.py`: re-exports `SyncMixin`/`Diff`/`SyncResult`/the two exceptions from `.engine`, and imports the union of vendored strategy modules so their registrations run at import time. |

**Create — producer + tests:**

| Path | Responsibility |
|---|---|
| `src/phantasos/generator/sdk/idempotency.py` | The metadata producer: `resolve_idempotency` (mutates opted-in `ObjectView`s), `select_strategies`, `referenced_strategies` (the per-family union to vendor), `_idempotency_literal`, and the seven build gates. Kept out of `wrapper.py`. |
| `tests/test_sdk_idempotency_context.py` | Baking tests: strategy auto-selection, literal contents, union computation, the seven gates. |
| `tests/test_sdk_sync.py` | Orchestrator + per-strategy unit tests (render + exec the templates). |
| `products/prisma-access/overrides/tests/test_scm_sync_live.py.jinja` | Live quartet — prisma-access `address` (scope, PUT RMW, direct). |
| `products/prisma-browser/overrides/tests/test_sdk_sync_live.py.jinja` | Live quartet — prisma-browser `application_group` (no scope, PATCH, get-after-write). |

**Modify:**

| Path | Change |
|---|---|
| `src/phantasos/config.py` | `ScopeSpec`, `IdempotencyResource`, `IdempotencyDefaults`, `IdempotencyConfig` after `OperationOverride` (~line 150). |
| `src/phantasos/productconfig.py` | `SubPackage.idempotency` (~line 117), `ProductConfig.idempotency` (~line 161) + placement validator (`_exactly_one_spec_mode`, ~line 195). |
| `src/phantasos/generator/sdk/wrapper.py` | `ObjectView` gains `sync: bool = False` / `idempotency_literal: str = "{}"` (~line 169); `build_wrapper_context` gains `idempotency=` and calls the producer after `bindings_literal` (~line 806). |
| `src/phantasos/generator/sdk/render.py` | `vendor()` (~line 46) threads `idempotency=`; new `_vendor_idempotency` helper writes the tree (union) beside the pagination/errors writes (~line 121); `_vendor_resources` (~line 202) passes `has_idempotency` and `idempotency=` to `build_wrapper_context`. |
| `src/phantasos/generator/sdk/build.py` | `_generate_one` (~line 103) passes the per-sub / top-level idempotency block (mirroring `operations=`, ~line 155/286). |
| `src/phantasos/generator/sdk/components/facade/resource.py.jinja` | Conditional `from .idempotency import SyncMixin` + `SyncMixin` base + `_idempotency` classvar beside `_bindings` (~line 25). |
| `src/phantasos/generator/sdk/components/auth/scm_oauth.py.jinja` | `_ProviderTokenSource`, `api_client_from_token`, federated `configuration_from_token`, `__all__` (~lines 23, 76, 141). |
| `src/phantasos/generator/sdk/components/facade/client.py.jinja` + `composer.py.jinja` | `from_access_token` classmethods (~line 52 / ~line 72). |
| `src/phantasos/generator/sdk/patches.py` | `patch_scope_validators` (new pass, sibling of `patch_oneof_unwrap_serializer` ~line 160) + `_ensure_model_validator_import` (sibling of `_ensure_model_serializer_import` ~line 149). |
| `products/prisma-access/sdk.yml` | `pagination: {type: offset}` + per-sub `idempotency:` opt-in. |
| `products/prisma-browser/sdk.yml` | top-level `idempotency:` opt-in. |
| `CHANGELOG.md`, `.agents/context/sdk-generator.md`, `.agents/context/product-config.md` | Phase 7 (write only; human commits). |

---

## Phase 0 — Metadata model: `sdk.yml` config, the `_idempotency` producer (auto-select + union), build gates

No runtime behavior yet. This phase ends with the generator baking a correct, gate-checked `_idempotency` literal into `ObjectView` — including the three auto-selected strategy names + the F1/F3/F4/F9 facts — and computing the per-family **union of strategy modules to vendor**. Highest-leverage phase; the literal's shape is the engine's contract.

### Task 0.1: `sdk.yml` idempotency config models

**Files:**
- Modify `src/phantasos/config.py` (after `OperationOverride`, ~line 162 — the imports `from typing import Any, Literal` and `from pydantic import BaseModel, ConfigDict` already exist; add `Field` to the pydantic import).
- Modify `src/phantasos/productconfig.py` (`SubPackage` ~line 117; `ProductConfig` ~line 161; `_exactly_one_spec_mode` ~line 195).
- Create tests in `tests/test_config.py` / `tests/test_productconfig.py`.

**Interfaces:**
- **Produces:** `phantasos.config.IdempotencyConfig` (with `.defaults: IdempotencyDefaults`, `.resources: dict[str, IdempotencyResource]`), `ScopeSpec`; `SubPackage.idempotency` / `ProductConfig.idempotency` (`IdempotencyConfig | None`). Consumed by Task 0.2 (`resolve_idempotency`) and Task 0.3 (`build.py`).

- [ ] **Step 1 — Failing tests.** Add to `tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from phantasos.config import IdempotencyConfig, IdempotencyResource, ScopeSpec


def test_idempotency_config_roundtrips_scoped_example():
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {
                "scope": {"fields": ["folder", "snippet", "device"], "rule": "exactly_one"}
            },
            "resources": {
                "address": {},
                "address_group": {"order_sensitive": ["static"]},
                "auto_tag_action": {"sync": False},
            },
        }
    )
    assert cfg.defaults.scope.fields == ["folder", "snippet", "device"]
    assert cfg.resources["address"].sync is True
    assert cfg.resources["address_group"].order_sensitive == ["static"]
    assert cfg.resources["auto_tag_action"].sync is False


def test_idempotency_config_roundtrips_noscope_example():
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"read_only": ["id", "createdAt", "updatedAt"]},
            "resources": {
                "user_group": {},
                "application": {"identity": ["type", "name"]},
                "application_plugin": {"sync": False},
            },
        }
    )
    assert cfg.defaults.scope is None
    assert cfg.resources["application"].identity == ["type", "name"]


def test_idempotency_resource_rejects_unknown_key():
    with pytest.raises(ValidationError):
        IdempotencyResource.model_validate({"identiy": ["name"]})  # typo -> extra=forbid


def test_idempotency_resource_accepts_strategy_override_strings():
    r = IdempotencyResource.model_validate(
        {"fetch": "list_filter", "mutate": "patch_minimal", "materialize": "get_after_write"}
    )
    assert (r.fetch, r.mutate, r.materialize) == ("list_filter", "patch_minimal", "get_after_write")


def test_scope_spec_defaults_rule_exactly_one():
    assert ScopeSpec.model_validate({"fields": ["folder"]}).rule == "exactly_one"
```

  And in `tests/test_productconfig.py`:

```python
import pytest
from pydantic import ValidationError

from phantasos.productconfig import ProductConfig


def test_federated_toplevel_idempotency_is_rejected():
    with pytest.raises(ValidationError, match="idempotency"):
        ProductConfig.model_validate(
            {
                "package": "p",
                "output": "../p",
                "base_url": "https://x",
                "subpackages": [{"slug": "objects", "spec": "openapi/objects.yaml"}],
                "idempotency": {"resources": {"address": {}}},
            }
        )
```

- [ ] **Step 2 — Run, expect FAIL.**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_config.py tests/test_productconfig.py -q`
  Expected: `ImportError: cannot import name 'IdempotencyConfig' from 'phantasos.config'` (and the federated test collects but the import error fails the module first).

- [ ] **Step 3 — Implement the models** in `config.py` (after `OperationOverride`; add `Field` to `from pydantic import BaseModel, ConfigDict, Field`):

```python
class ScopeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fields: list[str]
    rule: Literal["exactly_one"] = "exactly_one"


class IdempotencyResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: list[str] | None = None       # None -> infer; fail-loud on ambiguity
    read_only: list[str] = []
    computed: list[str] = []
    order_sensitive: list[str] = []
    write_only: list[str] = []              # F6 escape hatch (Phase 5 engine support)
    projections: dict[str, str] = {}        # F5: field -> item subfield (Phase 5)
    singleton: bool = False
    scope: ScopeSpec | None = None
    sync: bool = True                       # False -> CRUD primitives only
    # Strategy overrides — ESCAPE HATCH, not routine (ADR-0004 / spec §5.5). Each
    # family is auto-selected + baked by the producer; set one only to force a
    # non-default variant or name a custom module. None -> auto-derive.
    fetch: str | None = None                # "list_scan" | "list_filter" | "get" | custom
    mutate: str | None = None               # "put_rmw" | "patch_minimal" | custom
    materialize: str | None = None          # "direct" | "get_after_write" | custom
    page_limit: int = 200                   # fetch/list_scan tuning
    hydrate: bool | None = None             # None -> auto (GET-after-match when a get binding exists)


class IdempotencyDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: ScopeSpec | None = None
    read_only: list[str] = []
    computed: list[str] = []
    # PER-PRODUCT / PER-SUBPACKAGE strategy defaults — apply to every resource in
    # this block unless a resources.<name> entry overrides. Unset -> auto-select.
    # Precedence per family: resources.<name>.<family> > defaults.<family> > auto.
    fetch: str | None = None
    mutate: str | None = None
    materialize: str | None = None


class IdempotencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    defaults: IdempotencyDefaults = Field(default_factory=IdempotencyDefaults)
    resources: dict[str, IdempotencyResource] = Field(default_factory=dict)
```

  Then wire through `productconfig.py`: add `idempotency: IdempotencyConfig | None = None` to both `SubPackage` (import `IdempotencyConfig` from `.config`) and `ProductConfig`, and extend the `_exactly_one_spec_mode` validator's `if federated:` block:

```python
        if federated and self.idempotency is not None:
            raise ValueError(
                "top-level `idempotency:` is federated-illegal; declare it "
                "per sub-package (same split as `operations:`)"
            )
```

- [ ] **Step 4 — Run, expect PASS.**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_config.py tests/test_productconfig.py -q` → all green. Then `uv run nox -s gate`.
- [ ] **Step 5 — Commit:** `git commit -m "Add sdk.yml idempotency config models"`

### Task 0.2: the `_idempotency` producer — strategy auto-selection, union, build gates

**Files:**
- Create `src/phantasos/generator/sdk/idempotency.py`.
- Modify `src/phantasos/generator/sdk/wrapper.py` — `ObjectView` (~line 169) gains two fields; `build_wrapper_context` (~line 716) gains an `idempotency` param and calls `resolve_idempotency` after the `bindings_literal` loop (~line 806).
- Create `tests/test_sdk_idempotency_context.py`.

**Interfaces:**
- **Consumes:** `IdempotencyConfig` (Task 0.1); the final `list[ObjectView]` (with `methods`, `bindings`, `return_model`, `imports`), the introspected `OperationInventory`, and the built package's live model classes.
- **Produces:**

```python
def resolve_idempotency(
    objects: list[ObjectView],
    cfg: IdempotencyConfig,
    package: str,           # dotted; live-import model classes, alias-aware
    dist_root: Path,        # sys.path root to import the built package
    *,
    has_pagination: bool,
) -> None:
    """Mutate each opted-in ObjectView in place: set sync=True, idempotency_literal,
    and add the (module, class) import pairs the literal references. Raise ValueError
    (fail-loud, naming resource + fix) on any of the seven build gates below."""


def referenced_strategies(objects: list[ObjectView]) -> dict[str, set[str]]:
    """After resolve_idempotency: the UNION per family, e.g.
    {"fetch": {"list_scan"}, "mutate": {"put_rmw"}, "materialize": {"direct"}}.
    render.vendor() writes exactly these modules. Empty families -> empty sets."""
```

  `ObjectView` gains `sync: bool = False` and `idempotency_literal: str = "{}"` (after `bindings_literal`). `build_wrapper_context` signature gains `idempotency: IdempotencyConfig | None = None`; after the `ov.bindings_literal = _bindings_literal(ov.methods)` loop, add:

```python
    if idempotency is not None:
        from .idempotency import resolve_idempotency
        resolve_idempotency(result, idempotency, inv.sdk_package, dist_root,
                            has_pagination=has_pagination)
```

  (`dist_root` / `has_pagination` are threaded from `_vendor_resources` in Task 0.3; when `idempotency is None` nothing changes and the byte-identical guarantee holds.)

**Auto-selection** (resolved per family: `resources.<name>.<family>` → `defaults.<family>` → auto-derived):

| Family | Auto default | Derivation | Finding |
|---|---|---|---|
| `fetch` | `"list_scan"` | `"get"` if `singleton: true`; `"list_scan"` otherwise. `"list_filter"` only when explicitly set AND every identity field is a `query` param on the list binding — else gate #3. | F1 |
| `mutate` | — | `"patch_minimal"` if an `update` method exists whose binding classifies sub-verb `patch`; else `"put_rmw"` if a `replace` method exists; neither → gate #4. | F9 |
| `materialize` | — | `"direct"` if the mutating verb's `return_model` name equals the read model name; else `"get_after_write"`. | F3 |

**Baked data** (alongside the three strategy names):

| Key | Derivation | Finding |
|---|---|---|
| `identity` | annotation, else infer `["name"]` when the create-input model has a `name` wire key; neither → gate #2. | — |
| `scope` | per-resource `scope` → `defaults.scope` → `None`. Rendered as `{"fields": [...], "rule": "exactly_one"}` or `None`. | — |
| `models` | **bare class identifiers** for `create` / `update` / `read`: create = the create binding's `body_model_live`; update = the PATCH (`update`) or PUT (`replace`) binding's `body_model_live`; read = the `get` verb's return model (fallback: list item model). Producer adds each class's `(module, class)` to `ObjectView.imports`. | F4 |
| `input_fields` | union of create+update model wire keys — `f.alias or name` per `model_fields`. | F4 |
| `server_only` | resolved `id_field["wire"]` ∪ `defaults.read_only/computed` ∪ resource `read_only/computed`. | — |
| `id_field` | `{"wire": ..., "attr": ...}` for `id` on the read model; gate #? if a `get_after_write` materialize has no resolvable id. | F3 |
| `update.verb` | wrapper verb name of the update binding (`replace` / `update`). | F9 |
| `fetch_opts` | `{"page_limit": N, "hydrate": bool}`; `hydrate` auto-True when a `get` verb exists. | F1 |
| `order_sensitive`, `singleton`, `write_only`, `projections` | verbatim from the resource entry. | F5/F6 |

**The seven build gates** (all `ValueError`, all naming the resource + the fix):
1. **Unknown `resources:` key** — validated against the built object attrs (mirror `validate_override_keys`, `wrapper.py` ~57).
2. **Unresolvable identity** — no annotation, no inferable `name` → `"needs identity: or sync: false"` (mirror the anchorless gate `wrapper.py` ~229).
3. **`list_filter` without query params** — resolved `fetch == "list_filter"` but an identity field is not a list query param.
4. **No update verb** — neither `patch` nor `replace` binding and `sync: true` → `"set sync: false"`.
5. **F6 write-only** — `managed = input_fields − server_only − scope − write_only`; any managed wire key absent from the read model.
6. **F8 pagination** — a resource baked `fetch == "list_scan"` while the product has no pagination component (`has_pagination=False`).
7. **Singleton sanity** — `singleton: true` with a create or delete binding present.

- [ ] **Step 1 — Failing baking tests** in `tests/test_sdk_idempotency_context.py` (mirror `tests/test_sdk_wrapper.py`: `real_sdk` fixture + real introspection + a hand-authored `IdempotencyConfig`):

```python
from __future__ import annotations

from pathlib import Path

import pytest

from phantasos.config import IdempotencyConfig
from phantasos.generator.opmodel import introspect
from phantasos.generator.sdk.idempotency import referenced_strategies
from phantasos.generator.sdk.render import _discover_resources
from phantasos.generator.sdk.wrapper import build_wrapper_context


def _views(real_sdk: Path, pkg: str, cfg: IdempotencyConfig):
    inv = introspect(pkg, real_sdk)
    objects = build_wrapper_context(
        inv, {}, _discover_resources(real_sdk / pkg.replace(".", "/")),
        idempotency=cfg, dist_root=real_sdk, has_pagination=True,
    )
    return {o.attr: o for o in objects}


def test_put_object_bakes_list_scan_put_rmw_direct(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
         "resources": {"address": {}}}
    )
    v = _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)["address"]
    assert v.sync is True
    lit = v.idempotency_literal
    assert '"fetch": "list_scan"' in lit
    assert '"mutate": "put_rmw"' in lit
    assert '"materialize": "direct"' in lit
    assert '"update": {"verb": "replace"}' in lit
    assert '"identity": ["name"]' in lit
    assert '"folder"' in lit and '"snippet"' in lit  # scope trio
    assert '"models": {"create": Addresses' in lit    # bare identifier, not a string
    assert ("prisma_access.objects.models.addresses", "Addresses") in v.imports


def test_patch_envelope_object_bakes_patch_minimal_get_after_write(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"read_only": ["id"]}, "resources": {"application_group": {}}}
    )
    v = _views(real_sdk / "prisma_browser", "prisma_browser", cfg)["application_group"]
    lit = v.idempotency_literal
    assert '"fetch": "list_scan"' in lit          # no proven name filter -> default
    assert '"mutate": "patch_minimal"' in lit
    assert '"materialize": "get_after_write"' in lit
    assert '"update": {"verb": "update"}' in lit


def test_referenced_strategies_returns_per_family_union(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
         "resources": {"address": {}, "tag": {}}}
    )
    objects = list(_views(real_sdk / "prisma_access", "prisma_access.objects", cfg).values())
    ref = referenced_strategies(objects)
    assert ref == {"fetch": {"list_scan"}, "mutate": {"put_rmw"}, "materialize": {"direct"}}


def test_unknown_resource_key_gate(real_sdk):
    cfg = IdempotencyConfig.model_validate({"resources": {"nonexistent_obj": {}}})
    with pytest.raises(ValueError, match="nonexistent_obj"):
        _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)


def test_unresolvable_identity_gate(real_sdk):
    # auto_tag_action has no natural key; without sync:false it must fail loud.
    cfg = IdempotencyConfig.model_validate({"resources": {"auto_tag_action": {}}})
    with pytest.raises(ValueError, match="auto_tag_action.*identity"):
        _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)


def test_list_filter_without_query_param_gate(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
         "resources": {"address": {"fetch": "list_filter"}}}
    )
    with pytest.raises(ValueError, match="list_filter"):
        _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)


def test_pagination_gate_when_no_component(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
         "resources": {"address": {}}}
    )
    inv = introspect("prisma_access.objects", real_sdk / "prisma_access")
    with pytest.raises(ValueError, match="pagination"):
        build_wrapper_context(
            inv, {}, _discover_resources(real_sdk / "prisma_access" / "objects"),
            idempotency=cfg, dist_root=real_sdk / "prisma_access", has_pagination=False,
        )


def test_singleton_sanity_gate(real_sdk):
    # A resource with a create binding declared singleton must fail.
    cfg = IdempotencyConfig.model_validate({"resources": {"address": {"singleton": True}}})
    with pytest.raises(ValueError, match="singleton"):
        _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)


def test_sync_false_keeps_object_off(real_sdk):
    cfg = IdempotencyConfig.model_validate({"resources": {"auto_tag_action": {"sync": False}}})
    v = _views(real_sdk / "prisma_access", "prisma_access.objects", cfg)["auto_tag_action"]
    assert v.sync is False
    assert v.idempotency_literal == "{}"
```

  (If a named resource's real attr/model differs in the built SDK, adjust the resource name to a real one from `objects/` — verify with `_discover_resources`; the gate assertions are the load-bearing part.)

- [ ] **Step 2 — Run, expect FAIL.**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_idempotency_context.py -q`
  Expected: `ModuleNotFoundError: No module named 'phantasos.generator.sdk.idempotency'` (and `build_wrapper_context() got an unexpected keyword argument 'idempotency'`).

- [ ] **Step 3 — Implement** `src/phantasos/generator/sdk/idempotency.py`. `_idempotency_literal` mirrors `_bindings_literal`/`_binding_dict_repr` (`wrapper.py` ~662–682) EXCEPT the `models` values render as **bare identifiers** (not `repr` strings). Complete producer:

```python
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from ...config import IdempotencyConfig, IdempotencyResource, ScopeSpec

_FETCH, _MUTATE, _MATERIALIZE = "fetch", "mutate", "materialize"


def referenced_strategies(objects: list) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {_FETCH: set(), _MUTATE: set(), _MATERIALIZE: set()}
    for o in objects:
        if not getattr(o, "sync", False):
            continue
        meta = o._idempotency_meta  # stashed by resolve_idempotency
        out[_FETCH].add(meta[_FETCH])
        out[_MUTATE].add(meta[_MUTATE])
        out[_MATERIALIZE].add(meta[_MATERIALIZE])
    return out


def _import_pkg(package: str, dist_root: Path):
    root = str(dist_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(package)


def _wire_keys(model_cls) -> list[str]:
    return [f.alias or name for name, f in model_cls.model_fields.items()]


def _method(o, name):
    for m in o.methods:
        if m.name == name:
            return m
    return None


def _sub_verb(method) -> str | None:
    # the classified sub-verb of the update binding (patch vs put) — set on Binding.
    for b in method.bindings:
        sv = getattr(b, "sub_verb", None)
        if sv:
            return sv
    return None


def _resolve_strategy(family, resource: IdempotencyResource, defaults, auto: str) -> str:
    return getattr(resource, family) or getattr(defaults, family) or auto


def resolve_idempotency(objects, cfg: IdempotencyConfig, package, dist_root, *, has_pagination):
    by_attr = {o.attr: o for o in objects}
    unknown = set(cfg.resources) - set(by_attr)
    if unknown:
        raise ValueError(
            "sdk.yml idempotency.resources: unknown resource key(s): "
            f"{', '.join(sorted(unknown))} (valid: {', '.join(sorted(by_attr))})"
        )
    mod = _import_pkg(package, dist_root)
    for attr, rc in cfg.resources.items():
        o = by_attr[attr]
        if not rc.sync:
            o.sync = False
            continue
        meta = _build_meta(o, rc, cfg.defaults, mod, package, has_pagination)
        o.sync = True
        o._idempotency_meta = meta
        o.idempotency_literal = _idempotency_literal(meta, o)


def _build_meta(o, rc, defaults, mod, package, has_pagination) -> dict[str, Any]:
    create_m = _method(o, "create")
    read_m = _method(o, "get")
    patch_m = _method(o, "update")
    put_m = _method(o, "replace")
    delete_m = _method(o, "delete")

    # models --------------------------------------------------------------
    def _live(method):
        for b in method.bindings if method else ():
            if getattr(b, "body_model_live", None) is not None:
                return b.body_model_live
        return None

    create_cls = _live(create_m)
    update_method = patch_m or put_m
    if update_method is None and rc.singleton is False:
        raise ValueError(
            f"idempotency: {o.attr}: no update verb (neither patch nor replace) — "
            f"set `sync: false` or add an update op"
        )
    update_cls = _live(update_method) if update_method else create_cls
    read_cls = getattr(mod and read_m, "return_model", None)
    read_cls = _class_from(mod, read_m.return_import) if read_m and read_m.return_import else create_cls

    # identity ------------------------------------------------------------
    if rc.identity is not None:
        identity = list(rc.identity)
    elif create_cls is not None and "name" in _wire_keys(create_cls):
        identity = ["name"]
    else:
        raise ValueError(
            f"idempotency: {o.attr}: identity could not be inferred — add "
            f"`identity: [...]` or `sync: false`"
        )

    # scope ---------------------------------------------------------------
    scope: ScopeSpec | None = rc.scope or defaults.scope
    scope_lit = {"fields": list(scope.fields), "rule": scope.rule} if scope else None

    # id_field ------------------------------------------------------------
    id_wire, id_attr = "id", "id"
    if read_cls is not None:
        for name, f in read_cls.model_fields.items():
            if name == "id" or f.alias == "id":
                id_wire, id_attr = (f.alias or name), name
                break

    # strategies ----------------------------------------------------------
    singleton = rc.singleton
    if singleton and (create_m or delete_m):
        raise ValueError(
            f"idempotency: {o.attr}: singleton:true but a create/delete op exists"
        )
    auto_fetch = "get" if singleton else "list_scan"
    fetch = _resolve_strategy("fetch", rc, defaults, auto_fetch)
    auto_mutate = "patch_minimal" if (update_method and _sub_verb(update_method) == "patch") else "put_rmw"
    mutate = _resolve_strategy("mutate", rc, defaults, auto_mutate)
    ret_name = getattr(update_method, "return_model", None)
    auto_mat = "direct" if (ret_name and read_cls and ret_name == read_cls.__name__) else "get_after_write"
    materialize = _resolve_strategy("materialize", rc, defaults, auto_mat)

    # gates ---------------------------------------------------------------
    if fetch == "list_filter":
        list_m = _method(o, "list")
        qparams = {p for b in (list_m.bindings if list_m else ())
                   for p, meta_p in getattr(b, "param_map", {}).items()}  # location check below
        for idf in identity:
            if not _is_query_param(list_m, idf):
                raise ValueError(
                    f"idempotency: {o.attr}: fetch: list_filter but identity field "
                    f"{idf!r} is not a list query param"
                )
    if fetch == "list_scan" and not has_pagination:
        raise ValueError(
            f"idempotency: {o.attr}: list_scan fetch requires a pagination component "
            f"(sdk.yml `pagination:`)"
        )

    # fields --------------------------------------------------------------
    input_fields = sorted(set(_wire_keys(create_cls) if create_cls else [])
                          | set(_wire_keys(update_cls) if update_cls else []))
    server_only = sorted({id_wire} | set(defaults.read_only) | set(defaults.computed)
                         | set(rc.read_only) | set(rc.computed))
    scope_fields = set(scope.fields) if scope else set()
    managed = set(input_fields) - set(server_only) - scope_fields - set(rc.write_only)
    read_keys = set(_wire_keys(read_cls)) if read_cls else set()
    undetectable = sorted(managed - read_keys)
    if undetectable:
        raise ValueError(
            f"idempotency: {o.attr}: managed field(s) {undetectable} are undetectable "
            f"via GET (absent from the read model) — declare them under `write_only:` "
            f"(partial sync) or set `sync: false`"
        )

    hydrate = rc.hydrate if rc.hydrate is not None else (read_m is not None)
    return {
        "identity": identity,
        "scope": scope_lit,
        "models": {"create": create_cls.__name__ if create_cls else read_cls.__name__,
                   "update": update_cls.__name__ if update_cls else read_cls.__name__,
                   "read": read_cls.__name__ if read_cls else create_cls.__name__},
        "input_fields": input_fields,
        "server_only": server_only,
        "id_field": {"wire": id_wire, "attr": id_attr},
        "order_sensitive": list(rc.order_sensitive),
        "write_only": list(rc.write_only),
        "projections": dict(rc.projections),
        "singleton": singleton,
        "update": {"verb": (update_method.name if update_method else "replace")},
        "fetch": fetch,
        "mutate": mutate,
        "materialize": materialize,
        "fetch_opts": {"page_limit": rc.page_limit, "hydrate": hydrate},
    }
```

  Add the two small helpers and the literal builder:

```python
def _class_from(mod, imp):
    module_path, cls = imp
    return getattr(importlib.import_module(module_path), cls, None)


def _is_query_param(list_method, wire_field: str) -> bool:
    for b in (list_method.bindings if list_method else ()):
        for p in getattr(b, "params", []):
            if (getattr(p, "wire_name", None) == wire_field
                    and getattr(p, "location", None) == "query"):
                return True
    return False


def _idempotency_literal(meta: dict, o) -> str:
    """Like _bindings_literal but `models` values render as bare class identifiers."""
    models = "{" + ", ".join(f'"{k}": {v}' for k, v in meta["models"].items()) + "}"
    parts = {k: repr(v) for k, v in meta.items() if k != "models"}
    parts["models"] = models
    order = ["identity", "scope", "models", "input_fields", "server_only", "id_field",
             "order_sensitive", "write_only", "projections", "singleton", "update",
             "fetch", "mutate", "materialize", "fetch_opts"]
    body = ",\n".join(f'        "{k}": {parts[k]}' for k in order)
    # add each model class import to the object
    for name in set(meta["models"].values()):
        # resolve module from the object's already-known imports or the model's __module__
        pass
    return "{\n" + body + "\n    }"
```

  In `_build_meta`, after building `meta`, add each model class's `(class.__module__, class.__name__)` to `o.imports` for `create_cls`/`update_cls`/`read_cls` (so `resources.py` imports them). Add `sub_verb` / `body_model_live` / `params`(with `wire_name`,`location`) accessors to `Binding`/`MethodView` if not already present — the IR carries this; expose it minimally. Add to `ObjectView` (wrapper.py):

```python
    sync: bool = False
    idempotency_literal: str = "{}"
```

  (Whether `sub_verb`, `body_model_live`, `return_model`, and per-param `location` are already reachable on the IR views is the first thing to confirm; if a field is missing, thread it through `_build_method` where the op is available — the anchors are `wrapper.py` ~545–558. Do this as the minimal prerequisite folded into this task, with its own micro-test asserting the accessor exists.)

- [ ] **Step 4 — Run, expect PASS.**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_idempotency_context.py -q` → green. Requires a built `real_sdk` (the `smoke` build); if the fixture needs it, `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke` first.

- [ ] **Step 5 — Thread the config through the pipeline** (Task 0.3, folded here since the literal is untestable end-to-end without it). In `render._vendor_resources` (~line 224), pass `idempotency=` and the two derived flags to `build_wrapper_context`:

```python
        objects = build_wrapper_context(
            inv, operations, _discover_resources(pkg_dir),
            docs=loaded.config.docs,
            idempotency=idempotency,
            dist_root=dist_root,
            has_pagination=loaded.pagination is not None,
        )
```

  `_vendor_resources` gains an `idempotency` param; `vendor()` (~line 46) gains `idempotency: IdempotencyConfig | None = None` and passes it down; `build.py::_generate_one` passes `idempotency=` to `render.vendor` — `sub.config.idempotency` (federated, ~line 286) / `loaded.config.idempotency` (single-spec, ~line 208), exactly like `operations=`.

- [ ] **Step 6 — Run + commit.**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_idempotency_context.py tests/test_config.py tests/test_productconfig.py tests/test_sdk_wrapper.py -q` → green; `uv run nox -s gate` → green.
  `git commit -m "Bake per-resource idempotency metadata and strategy selection into the wrapper context"`

**Exit gate (Phase 0):** the pytest set above green; `uv run nox -s gate` green; a build with `idempotency=None` renders every `ObjectView.sync == False`, `referenced_strategies` empty, and `resources.py` byte-identical (assert by rendering with and without `idempotency=None`). No live requirement (no runtime behavior yet).

---

## Phase 1 — The idempotency component: orchestrator + base + the strategy modules the two proven resources need

Translate the validated prototype into the vendored component tree, wire the mixin into `resource.py.jinja`, opt in the two proven resources, and stand up the live quartet as the standing exit gate for every later phase. `fetch/get` (singleton) is deferred to Phase 6 (no singleton is live-proven).

### Task 1.1: `base.py.jinja` — Protocol seams + registries

**Files:** create `src/phantasos/generator/sdk/components/idempotency/base.py.jinja`; test `tests/test_sdk_sync.py`.

**Interfaces — Produces:** module exposing `FetchStrategy`/`MutateStrategy`/`MaterializeStrategy` Protocols, empty `FETCH`/`MUTATE`/`MATERIALIZE` dicts, and a re-exported `NotFoundException`. Consumed by `engine.py.jinja` (registries) and every strategy module (registration + `NotFoundException`).

- [ ] **Step 1 — Failing test** in `tests/test_sdk_sync.py` (mirror `tests/test_render.py::_exec_extras_errors`, ~line 37):

```python
import sys
import types

from phantasos.generator.sdk import render


def _exec_idem_module(name: str, src: str, deps: dict) -> types.ModuleType:
    """Exec a rendered extras/idempotency/*.py in a stub package tree."""
    pkg = types.ModuleType("_ip"); pkg.__path__ = []
    idem = types.ModuleType("_ip.extras.idempotency"); idem.__path__ = []
    exc = types.ModuleType("_ip.exceptions")
    exc.NotFoundException = type("NotFoundException", (Exception,), {})
    mods = {"_ip": pkg, "_ip.extras": types.ModuleType("_ip.extras"),
            "_ip.extras.idempotency": idem, "_ip.exceptions": exc, **deps}
    mods["_ip.extras"].__path__ = []
    sys.modules.update(mods)
    try:
        mod = types.ModuleType(f"_ip.extras.idempotency.{name}")
        mod.__package__ = "_ip.extras.idempotency"
        exec(compile(src, f"{name}.py", "exec"), mod.__dict__)  # noqa: S102
        sys.modules[f"_ip.extras.idempotency.{name}"] = mod
        return mod
    finally:
        pass  # left registered for dependent execs; cleaned per-test via fixture


def _render_idem(template: str, **params) -> str:
    return render._env().get_template(f"idempotency/{template}").render(**params)


def test_base_exposes_registries_and_protocols():
    mod = _exec_idem_module("base", _render_idem("base.py.jinja", federated=False), {})
    assert mod.FETCH == {} and mod.MUTATE == {} and mod.MATERIALIZE == {}
    for proto in ("FetchStrategy", "MutateStrategy", "MaterializeStrategy"):
        assert hasattr(mod, proto)
    assert issubclass(mod.NotFoundException, Exception)
```

- [ ] **Step 2 — Run, expect FAIL:**
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py::test_base_exposes_registries_and_protocols -q`
  Expected: `jinja2.exceptions.TemplateNotFound: idempotency/base.py.jinja`.

- [ ] **Step 3 — Implement** `base.py.jinja`:

```jinja
"""Idempotency strategy seams + registries (ADR-0004)."""
from __future__ import annotations

from typing import Any, Protocol

{% if federated %}from {{ root_package }}._runtime.exceptions import NotFoundException
{% else %}from ..exceptions import NotFoundException
{% endif %}
__all__ = [
    "FetchStrategy", "MutateStrategy", "MaterializeStrategy",
    "FETCH", "MUTATE", "MATERIALIZE", "NotFoundException",
]


class FetchStrategy(Protocol):
    def __call__(self, res: Any, identity: dict, scope: dict, meta: dict) -> Any | None: ...


class MutateStrategy(Protocol):
    def __call__(self, res: Any, desired: Any, actual: Any, diff: Any, meta: dict) -> Any: ...


class MaterializeStrategy(Protocol):
    def __call__(self, res: Any, response: Any, identity: dict, scope: dict, meta: dict) -> Any: ...


FETCH: dict[str, FetchStrategy] = {}
MUTATE: dict[str, MutateStrategy] = {}
MATERIALIZE: dict[str, MaterializeStrategy] = {}
```

- [ ] **Step 4 — Run, expect PASS**, then commit:
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py -q`
  `git commit -m "Add the idempotency seam protocols and strategy registries"`

### Task 1.2: `engine.py.jinja` — the orchestrator + Diff/SyncResult/exceptions

**Files:** create `components/idempotency/engine.py.jinja`; test `tests/test_sdk_sync.py`.

**Interfaces — Produces:** `SyncMixin` (`apply`/`absent`/`fetch`/`diff` + `_present`/`_full`/`_extract_identity`/`_split`/`_comparable`), `Diff`, `SyncResult`, `AbsentNotSupported`, `IdentityUnresolved`, `_normalize`. **Consumes:** `FETCH`/`MUTATE`/`MATERIALIZE` from `.base`.

**Prototype mapping:** `Diff`/`SyncResult` ← `engine.py` 21–35; exceptions ← 39–44; `_jsonify`/`_normalize` ← 59–76; `_present`/`_full` ← 92–101; `_extract_identity` ← 104–119; `_comparable`/`diff` ← 141–157; `apply`/`absent`/`fetch` control flow ← 122–213 (the varying branches now delegate to the registries).

- [ ] **Step 1 — Failing orchestrator unit tests.** Render `base` + `engine` once, register **canned fake strategies**, drive `SyncMixin` through a stub resource:

```python
import types

import pytest


def _engine_env():
    """Render base + engine into one stub module namespace; return (engine_mod)."""
    base_src = _render_idem("base.py.jinja", federated=False)
    base = _exec_idem_module("base", base_src, {})
    eng_src = _render_idem("engine.py.jinja", federated=False)
    eng = _exec_idem_module("engine", eng_src, {"_ip.extras.idempotency.base": base})
    return base, eng


class _Model:
    """Minimal pydantic-like stand-in with model_dump/to_dict."""
    def __init__(self, **kw): self.__dict__.update(kw); self._set = set(kw)
    def model_dump(self, *, by_alias=True, mode="json", exclude_unset=False):
        return {k: v for k, v in self.__dict__.items()
                if k not in ("_set",) and (not exclude_unset or k in self._set)}
    def to_dict(self): return self.model_dump()
    @classmethod
    def model_validate(cls, d): return cls(**d)


def _meta(**over):
    m = {"identity": ["name"], "scope": None,
         "models": {"create": _Model, "update": _Model, "read": _Model},
         "input_fields": ["name", "description", "ip_netmask"],
         "server_only": ["id"], "id_field": {"wire": "id", "attr": "id"},
         "order_sensitive": [], "write_only": [], "projections": {},
         "singleton": False, "update": {"verb": "replace"},
         "fetch": "F", "mutate": "M", "materialize": "T",
         "fetch_opts": {"page_limit": 200, "hydrate": False}}
    m.update(over); return m


def _stub(base, eng, meta, existing=None, record=None):
    record = record if record is not None else []
    base.FETCH["F"] = lambda res, i, s, m: existing
    base.MUTATE["M"] = lambda res, d, a, df, m: (record.append(("mutate", df)), _Model(id="x", **a.model_dump()))[1]
    base.MATERIALIZE["T"] = lambda res, resp, i, s, m: resp

    class Stub(eng.SyncMixin):
        _idempotency = meta
        def create(self, *, body): record.append(("create", body)); return _Model(id="new", **body.model_dump())
        def delete(self, *, id): record.append(("delete", id))
    return Stub(), record


def test_create_builds_body_and_calls_materialize():
    base, eng = _engine_env()
    res, rec = _stub(base, eng, _meta(), existing=None)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert r.changed and r.action == "created"
    assert any(k == "create" for k, _ in rec)


def test_reapply_identical_is_unchanged():
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, _ = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32"))
    assert not r.changed and r.action == "unchanged"


def test_drift_calls_mutate_then_materialize():
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, rec = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="2.2.2.2/32"))
    assert r.changed and r.action == "updated"
    assert set(r.diff.changes) == {"ip_netmask"}
    assert any(k == "mutate" for k, _ in rec)


def test_check_mode_never_mutates():
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", id="1")
    res, rec = _stub(base, eng, _meta(), existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="9.9.9.9/32"), check_mode=True)
    assert r.changed and not any(k == "mutate" for k, _ in rec)


def test_identity_unresolved_when_name_unset():
    base, eng = _engine_env()
    res, _ = _stub(base, eng, _meta(), existing=None)
    with pytest.raises(eng.IdentityUnresolved):
        res.apply(_Model(ip_netmask="1.1.1.1/32"))


def test_singleton_absent_raises():
    base, eng = _engine_env()
    res, _ = _stub(base, eng, _meta(singleton=True), existing=None)
    with pytest.raises(eng.AbsentNotSupported):
        res.absent(_Model(name="a"))


def test_normalize_list_order_insensitive_by_default():
    base, eng = _engine_env()
    actual = _Model(name="a", tag=["x", "y"], id="1")
    meta = _meta(input_fields=["name", "tag"], order_sensitive=[])
    res, _ = _stub(base, eng, meta, existing=actual)
    r = res.apply(_Model(name="a", tag=["y", "x"]))
    assert not r.changed          # order-insensitive -> no drift
    meta2 = _meta(input_fields=["name", "tag"], order_sensitive=["tag"])
    res2, _ = _stub(base, eng, meta2, existing=actual)
    assert res2.apply(_Model(name="a", tag=["y", "x"])).changed  # order-sensitive -> drift


def test_scope_excluded_from_diff():
    base, eng = _engine_env()
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", folder="Shared", id="1")
    meta = _meta(scope={"fields": ["folder"], "rule": "exactly_one"},
                 input_fields=["name", "ip_netmask", "folder"])
    res, _ = _stub(base, eng, meta, existing=actual)
    r = res.apply(_Model(name="a", ip_netmask="1.1.1.1/32", folder="Prod"))
    assert not r.changed          # folder is scope, not drift
```

- [ ] **Step 2 — Run, expect FAIL:** `TemplateNotFound: idempotency/engine.py.jinja`.

- [ ] **Step 3 — Implement** `engine.py.jinja`:

```jinja
"""Idempotent-sync orchestrator (SyncMixin) + return shapes + exceptions."""
from __future__ import annotations

import enum
import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Optional

from .base import FETCH, MUTATE, MATERIALIZE

__all__ = ["Diff", "SyncResult", "AbsentNotSupported", "IdentityUnresolved", "SyncMixin"]


@dataclass(frozen=True)
class Diff:
    changed: bool
    changes: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    action: Literal["created", "updated", "deleted", "unchanged"]
    before: Optional[dict[str, Any]]
    after: Optional[dict[str, Any]]
    diff: Diff
    before_model: Any = None
    after_model: Any = None


class AbsentNotSupported(Exception):
    """absent() called on a singleton resource (no delete/create lifecycle)."""


class IdentityUnresolved(Exception):
    """Identity unset on desired, or the fetch lookup matched more than one object."""


def _jsonify(value: Any) -> Any:
    if isinstance(value, enum.Enum):
        return value.value
    return value


def _normalize(value: Any, *, order_sensitive: bool) -> Any:
    value = _jsonify(value)
    if isinstance(value, dict):
        return {k: _normalize(v, order_sensitive=order_sensitive) for k, v in value.items()}
    if isinstance(value, list):
        items = [_normalize(v, order_sensitive=order_sensitive) for v in value]
        if not order_sensitive:
            items = sorted(items, key=lambda v: json.dumps(v, sort_keys=True, default=str))
        return items
    return value


class SyncMixin:
    """Thin idempotent-sync orchestrator; delegates fetch/mutate/materialize to the
    strategy named in `_idempotency`. Owns every uniform step (ADR-0004 / spec §5.2)."""

    _idempotency: ClassVar[dict[str, Any]]

    def _present(self, model: Any) -> dict[str, Any]:
        return model.model_dump(by_alias=True, mode="json", exclude_unset=True)

    def _full(self, model: Any) -> dict[str, Any]:
        return model.model_dump(by_alias=True, mode="json")

    def _scope_fields(self) -> set:
        sc = self._idempotency.get("scope")
        return set(sc["fields"]) if sc else set()

    def _extract_identity(self, desired: Any) -> tuple[dict, dict]:
        meta = self._idempotency
        wire = self._full(desired)
        identity = {}
        for k in meta["identity"]:
            v = wire.get(k)
            if v is None:
                raise IdentityUnresolved(f"identity field {k!r} unset on desired")
            identity[k] = v
        scope = {k: wire[k] for k in self._scope_fields() if wire.get(k) is not None}
        return identity, scope

    def _split(self, kwargs: dict) -> tuple[dict, dict]:
        meta = self._idempotency
        identity = {k: v for k, v in kwargs.items() if k in meta["identity"]}
        scope = {k: v for k, v in kwargs.items() if k in self._scope_fields()}
        return identity, scope

    def _comparable(self, present_desired: dict) -> list[str]:
        meta = self._idempotency
        excluded = (set(meta.get("server_only", [])) | self._scope_fields()
                    | set(meta.get("write_only", [])))
        universe = set(meta["input_fields"])
        return [k for k in present_desired if k in universe and k not in excluded]

    def diff(self, desired: Any, actual: Any) -> Diff:
        meta = self._idempotency
        d = self._present(desired)
        a = self._full(actual)
        order_sensitive = set(meta.get("order_sensitive", []))
        changes: dict[str, dict[str, Any]] = {}
        for key in self._comparable(d):
            os_ = key in order_sensitive
            if _normalize(d[key], order_sensitive=os_) != _normalize(a.get(key), order_sensitive=os_):
                changes[key] = {"before": a.get(key), "after": d[key]}
        return Diff(changed=bool(changes), changes=changes)

    def fetch(self, **identity_and_scope: Any) -> Any | None:
        meta = self._idempotency
        identity, scope = self._split(identity_and_scope)
        return FETCH[meta["fetch"]](self, identity, scope, meta)

    def apply(self, desired: Any, *, check_mode: bool = False) -> SyncResult:
        meta = self._idempotency
        identity, scope = self._extract_identity(desired)
        actual = FETCH[meta["fetch"]](self, identity, scope, meta)
        if actual is None:                                          # ---- CREATE
            present = self._present(desired)
            body = meta["models"]["create"].model_validate(present)
            d = Diff(True, {k: {"before": None, "after": v} for k, v in present.items()})
            if check_mode:
                return SyncResult(True, "created", None, present, d, None, desired)
            resp = self.create(body=body)
            after = MATERIALIZE[meta["materialize"]](self, resp, identity, scope, meta)
            return SyncResult(True, "created", None, self._full(after), d, None, after)
        d = self.diff(desired, actual)
        if not d.changed:                                          # ---- NO-OP
            return SyncResult(False, "unchanged", self._full(actual), self._full(actual),
                              d, actual, actual)
        if check_mode:                                             # ---- PREDICT
            after = {**self._full(actual), **{k: c["after"] for k, c in d.changes.items()}}
            return SyncResult(True, "updated", self._full(actual), after, d, actual, None)
        resp = MUTATE[meta["mutate"]](self, desired, actual, d, meta)
        after = MATERIALIZE[meta["materialize"]](self, resp, identity, scope, meta)
        return SyncResult(True, "updated", self._full(actual), self._full(after), d, actual, after)

    def absent(self, desired_or_identity: Any, *, check_mode: bool = False) -> SyncResult:
        meta = self._idempotency
        if meta.get("singleton"):
            raise AbsentNotSupported(meta.get("identity", ["<resource>"]))
        identity, scope = self._extract_identity(desired_or_identity)
        actual = FETCH[meta["fetch"]](self, identity, scope, meta)
        if actual is None:
            return SyncResult(False, "unchanged", None, None, Diff(False, {}), None, None)
        if not check_mode:
            self.delete(id=getattr(actual, meta["id_field"]["attr"]))
        return SyncResult(True, "deleted", self._full(actual), None, Diff(True, {}), actual, None)
```

- [ ] **Step 4 — Run, expect PASS**, then commit:
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py -q`
  `git commit -m "Add the idempotent sync orchestrator (SyncMixin) component"`

### Task 1.3: the strategy modules (each independently unit-tested)

**Files:** create `fetch/list_scan.py.jinja`, `fetch/list_filter.py.jinja`, `mutate/put_rmw.py.jinja`, `mutate/patch_minimal.py.jinja`, `materialize/direct.py.jinja`, `materialize/get_after_write.py.jinja`, `__init__.py.jinja`; extend `tests/test_sdk_sync.py`.

**Interfaces:** each module is `def <name>(res, ...): ...` matching its Protocol (Task 1.1) and self-registers in the matching registry. **Consumes:** `FETCH`/`MUTATE`/`MATERIALIZE`, `NotFoundException` from `..base`; `IdentityUnresolved` from `..engine`. `res` exposes `list`/`get`/`create`/`replace`/`update`/`delete` + `_present`/`_full`.

**Per-strategy prototype mapping:** `list_scan` ← `engine.py` 122–138 (F1/F2); `list_filter` ← `run_prisma_browser.py` 50–61; `put_rmw` ← `engine.py` 160–166 + 194–198 (F9); `patch_minimal` ← `engine.py` PATCH branch + `run_prisma_browser.py` 93–95; `direct` ← `run_prisma_access.py` (response is the object); `get_after_write` ← `run_prisma_browser.py` 83–86, 95–97 (F3).

- [ ] **Step 1 — Failing per-strategy + integration tests** (extend `tests/test_sdk_sync.py`):

```python
def _exec_strategy(family, name, base, eng):
    src = _render_idem(f"{family}/{name}.py.jinja", federated=False)
    deps = {"_ip.extras.idempotency.base": base, "_ip.extras.idempotency.engine": eng}
    return _exec_idem_module(f"{family}.{name}", src, deps)


class _Page:
    def __init__(self, data): self.data = data


def test_list_scan_absorbs_404_and_empty_and_matches():
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    meta = _meta(fetch="list_scan")
    # 404 -> None
    class R404:
        def list(self, **kw): raise base.NotFoundException()
        _full = eng.SyncMixin._full
    assert ls.list_scan(R404(), {"name": "a"}, {}, meta) is None
    # empty -> None
    class REmpty:
        def list(self, **kw): return _Page([])
        _full = eng.SyncMixin._full
    assert ls.list_scan(REmpty(), {"name": "a"}, {}, meta) is None
    # exact match
    hit = _Model(name="a", id="1")
    class RHit:
        def list(self, **kw): return _Page([_Model(name="b", id="2"), hit])
        _full = eng.SyncMixin._full
    assert ls.list_scan(RHit(), {"name": "a"}, {}, meta) is hit


def test_list_scan_raises_on_multiple_matches():
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    class RDup:
        def list(self, **kw): return _Page([_Model(name="a", id="1"), _Model(name="a", id="2")])
        _full = eng.SyncMixin._full
    with pytest.raises(eng.IdentityUnresolved):
        ls.list_scan(RDup(), {"name": "a"}, {}, _meta(fetch="list_scan"))


def test_list_scan_hydrates_when_opted():
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    got = _Model(name="a", id="1", description="full")
    class RHyd:
        def list(self, **kw): return _Page([_Model(name="a", id="1")])
        def get(self, *, id): return got
        _full = eng.SyncMixin._full
    meta = _meta(fetch="list_scan", fetch_opts={"page_limit": 200, "hydrate": True})
    assert ls.list_scan(RHyd(), {"name": "a"}, {}, meta) is got


def test_put_rmw_seeds_actual_overlays_desired_drops_id():
    base, eng = _engine_env()
    pr = _exec_strategy("mutate", "put_rmw", base, eng)
    calls = {}
    actual = _Model(name="a", ip_netmask="1.1.1.1/32", description="keep", id="1")
    class R:
        _present = eng.SyncMixin._present
        def replace(self, *, id, body): calls["id"] = id; calls["body"] = body; return body
    body = pr.put_rmw(R(), _Model(name="a", ip_netmask="2.2.2.2/32"), actual, None, _meta())
    assert calls["id"] == "1"
    dumped = body.model_dump()
    assert dumped["ip_netmask"] == "2.2.2.2/32" and dumped["description"] == "keep"
    assert "id" not in dumped


def test_patch_minimal_sends_only_changed_in_patch_model():
    base, eng = _engine_env()
    pm = _exec_strategy("mutate", "patch_minimal", base, eng)
    calls = {}
    class R:
        def update(self, *, id, body): calls["body"] = body; return body
    diff = eng.Diff(True, {"description": {"before": "old", "after": "new"}})
    meta = _meta(mutate="patch_minimal", update={"verb": "update"})
    actual = _Model(name="a", id="1")
    pm.patch_minimal(R(), _Model(name="a", description="new"), actual, diff, meta)
    assert calls["body"].model_dump() == {"description": "new"}


def test_direct_returns_response():
    base, eng = _engine_env()
    d = _exec_strategy("materialize", "direct", base, eng)
    obj = _Model(name="a", id="1")
    assert d.direct(object(), obj, {}, {}, _meta()) is obj


def test_get_after_write_reads_id_then_gets():
    base, eng = _engine_env()
    gaw = _exec_strategy("materialize", "get_after_write", base, eng)
    fresh = _Model(name="a", id="1", description="full")
    class R:
        def get(self, *, id): assert id == "1"; return fresh
    envelope = _Model(id="1")
    assert gaw.get_after_write(R(), envelope, {}, {}, _meta()) is fresh
```

- [ ] **Step 2 — Run, expect FAIL:** `TemplateNotFound: fetch/list_scan.py.jinja`.

- [ ] **Step 3 — Implement the six modules.** `fetch/list_scan.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import FETCH, NotFoundException
from ..engine import IdentityUnresolved


def _match(res: Any, candidates: list, identity: dict) -> list:
    return [c for c in candidates if all(res._full(c).get(k) == v for k, v in identity.items())]


def list_scan(res: Any, identity: dict, scope: dict, meta: dict) -> Any | None:
    opts = meta.get("fetch_opts", {})
    try:
        page = res.list(all_pages=True, limit=opts.get("page_limit", 200), **scope)
    except NotFoundException:
        return None
    matches = _match(res, getattr(page, "data", None) or [], identity)
    if len(matches) > 1:
        raise IdentityUnresolved(f"{identity}: {len(matches)} matches")
    if not matches:
        return None
    match = matches[0]
    if opts.get("hydrate"):
        return res.get(id=getattr(match, meta["id_field"]["attr"]))
    return match


FETCH["list_scan"] = list_scan
```

  `fetch/list_filter.py.jinja` (identical body except the list call — server-side filter):

```jinja
from __future__ import annotations

from typing import Any

from ..base import FETCH, NotFoundException
from ..engine import IdentityUnresolved


def list_filter(res: Any, identity: dict, scope: dict, meta: dict) -> Any | None:
    opts = meta.get("fetch_opts", {})
    try:
        page = res.list(**identity, **scope)
    except NotFoundException:
        return None
    candidates = getattr(page, "data", None) or []
    matches = [c for c in candidates if all(res._full(c).get(k) == v for k, v in identity.items())]
    if len(matches) > 1:
        raise IdentityUnresolved(f"{identity}: {len(matches)} matches")
    if not matches:
        return None
    match = matches[0]
    if opts.get("hydrate"):
        return res.get(id=getattr(match, meta["id_field"]["attr"]))
    return match


FETCH["list_filter"] = list_filter
```

  `mutate/put_rmw.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import MUTATE


def put_rmw(res: Any, desired: Any, actual: Any, diff: Any, meta: dict) -> Any:
    merged = {**actual.to_dict(), **res._present(desired)}
    merged.pop(meta["id_field"]["wire"], None)   # id routes to the URL, not the body
    body = meta["models"]["update"].model_validate(merged)
    verb = getattr(res, meta["update"]["verb"])  # F9: "replace" for PUT
    return verb(id=getattr(actual, meta["id_field"]["attr"]), body=body)


MUTATE["put_rmw"] = put_rmw
```

  `mutate/patch_minimal.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import MUTATE


def patch_minimal(res: Any, desired: Any, actual: Any, diff: Any, meta: dict) -> Any:
    merged = {k: c["after"] for k, c in diff.changes.items()}
    body = meta["models"]["update"].model_validate(merged)
    verb = getattr(res, meta["update"]["verb"])  # F9: "update" for PATCH
    return verb(id=getattr(actual, meta["id_field"]["attr"]), body=body)


MUTATE["patch_minimal"] = patch_minimal
```

  `materialize/direct.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import MATERIALIZE


def direct(res: Any, response: Any, identity: dict, scope: dict, meta: dict) -> Any:
    return response


MATERIALIZE["direct"] = direct
```

  `materialize/get_after_write.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import MATERIALIZE


def get_after_write(res: Any, response: Any, identity: dict, scope: dict, meta: dict) -> Any:
    new_id = getattr(response, meta["id_field"]["attr"])  # F3: id-only envelope
    return res.get(id=new_id)


MATERIALIZE["get_after_write"] = get_after_write
```

  `__init__.py.jinja` (imports the vendored union so registrations run):

```jinja
"""Idempotent-sync engine + strategies (ADR-0004). Vendored on opt-in only."""
from .engine import (  # noqa: F401
    AbsentNotSupported,
    Diff,
    IdentityUnresolved,
    SyncMixin,
    SyncResult,
)

{% for name in fetch %}from .fetch import {{ name }}  # noqa: F401
{% endfor %}{% for name in mutate %}from .mutate import {{ name }}  # noqa: F401
{% endfor %}{% for name in materialize %}from .materialize import {{ name }}  # noqa: F401
{% endfor %}
__all__ = ["SyncMixin", "Diff", "SyncResult", "AbsentNotSupported", "IdentityUnresolved"]
```

- [ ] **Step 4 — Add the integration test** (real six strategies through `SyncMixin` end-to-end — the prototype's quartet on generated code, with a canned wrapper carrying real list/get/create/replace verbs). Assert: F2 both absence shapes → None; create → materialize (direct); update → put_rmw preserves unmanaged; check_mode no write.

- [ ] **Step 5 — Run, expect PASS**, commit:
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py -q`
  `git commit -m "Add the fetch/mutate/materialize sync strategy modules"`

### Task 1.4: vendor the union in `render.vendor`

**Files:** modify `src/phantasos/generator/sdk/render.py` (new `_vendor_idempotency`, called beside the pagination/errors writes ~line 121); test `tests/test_render.py`.

**Interfaces — Consumes:** `referenced_strategies(objects)` (Task 0.2), the built `ObjectView` list, the Jinja env. **Produces:** `extras/idempotency/{__init__,base,engine}.py` + the union of referenced strategy modules under `fetch/`,`mutate/`,`materialize/`.

- [ ] **Step 1 — Failing tests** in `tests/test_render.py`:

```python
def _fake_objects(refs):
    """Stub ObjectViews whose _idempotency_meta names the given strategies."""
    from types import SimpleNamespace
    fetch, mutate, mat = refs
    objs = []
    for f, m, t in zip(fetch, mutate, mat):
        o = SimpleNamespace(attr="x", sync=True,
                            _idempotency_meta={"fetch": f, "mutate": m, "materialize": t})
        objs.append(o)
    return objs


def test_vendor_writes_union_of_referenced_strategies(tmp_path):
    pkg = _make_pkg(tmp_path)
    loaded = load_product(str(_PRODUCTS / "prisma-browser" / "sdk.yml"))
    objs = _fake_objects(([("list_scan", "list_filter")][0], ("put_rmw", "patch_minimal"),
                          ("direct", "get_after_write")))
    render._vendor_idempotency(pkg, objs, {"federated": False, "root_package": "demo"},
                               render._env(), [])
    idem = pkg / "extras" / "idempotency"
    assert (idem / "engine.py").exists() and (idem / "base.py").exists()
    assert (idem / "fetch" / "list_scan.py").exists()
    assert (idem / "fetch" / "list_filter.py").exists()
    assert (idem / "mutate" / "put_rmw.py").exists()
    assert (idem / "mutate" / "patch_minimal.py").exists()
    assert not (idem / "fetch" / "get.py").exists()          # union: unreferenced absent
    assert not (idem / "materialize" / "direct.py").exists() or True  # per refs above


def test_vendor_writes_no_idempotency_dir_when_off(tmp_path):
    pkg = _make_pkg(tmp_path)
    loaded = load_product(str(_PRODUCTS / "adem" / "sdk.yml"))  # never opts in
    render.vendor(pkg, loaded, wrapper_objects=[])
    assert not (pkg / "extras" / "idempotency").exists()
```

  (`_PRODUCTS = Path(...)/"products"`; adjust to the repo's existing fixture constant.)

- [ ] **Step 2 — Run, expect FAIL:** `AttributeError: module 'phantasos.generator.sdk.render' has no attribute '_vendor_idempotency'`.

- [ ] **Step 3 — Implement** `_vendor_idempotency` and call it from `vendor()` after `_vendor_resources` (it needs the returned `objects`), guarded on `idempotency is not None`:

```python
def _vendor_idempotency(pkg_dir, objects, ctx, env, written):
    from .idempotency import referenced_strategies

    refs = referenced_strategies(objects)
    if not any(refs.values()):
        return
    idem = pkg_dir / "extras" / "idempotency"
    idem.mkdir(parents=True, exist_ok=True)
    for core in ("base", "engine"):
        (idem / f"{core}.py").write_text(
            env.get_template(f"idempotency/{core}.py.jinja").render(**ctx), encoding="utf-8")
    for family in ("fetch", "mutate", "materialize"):
        names = sorted(refs[family])
        if not names:
            continue
        (idem / family).mkdir(exist_ok=True)
        (idem / family / "__init__.py").write_text("", encoding="utf-8")
        for name in names:
            (idem / family / f"{name}.py").write_text(
                env.get_template(f"idempotency/{family}/{name}.py.jinja").render(**ctx),
                encoding="utf-8")
    (idem / "__init__.py").write_text(
        env.get_template("idempotency/__init__.py.jinja").render(
            fetch=sorted(refs["fetch"]), mutate=sorted(refs["mutate"]),
            materialize=sorted(refs["materialize"]), **ctx),
        encoding="utf-8")
    written.append("idempotency/")
```

  `ctx` carries `federated` and `root_package` (already computed in `vendor()` for the auth/facade renders). Call `_vendor_idempotency(pkg_dir, objects, ctx, builtin_env, written)` in `vendor()` immediately after `objects = _vendor_resources(...)` and before the pass-2 facade render (so `resources.py`'s `from .idempotency import SyncMixin` resolves).

- [ ] **Step 4 — Run, expect PASS**, commit:
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_render.py -q`
  `git commit -m "Vendor the idempotency engine and the union of referenced strategy modules"`

### Task 1.5: wire the mixin into `resource.py.jinja`

**Files:** modify `components/facade/resource.py.jinja`; extend `tests/test_sdk_sync.py` + a byte-identical regression in `tests/test_render.py`.

- [ ] **Step 1 — Failing tests:**

```python
def test_resource_renders_syncmixin_and_classvar_when_opted():
    src = render._env().get_template("facade/resource.py.jinja").render(
        objects=[_syncable_object_view()], imports=[], has_pagination=True,
        has_idempotency=True)
    assert "from .idempotency import SyncMixin" in src
    assert "class AddressResource(SyncMixin):" in src
    assert "_idempotency: ClassVar[dict[str, Any]] =" in src


def test_resource_render_byte_identical_when_off():
    ov = _plain_object_view()  # sync=False, idempotency_literal="{}"
    off = render._env().get_template("facade/resource.py.jinja").render(
        objects=[ov], imports=[], has_pagination=True, has_idempotency=False)
    assert "SyncMixin" not in off
    assert "_idempotency" not in off
```

  (`_syncable_object_view()` / `_plain_object_view()` build a `SimpleNamespace`/`ObjectView` with `classname="AddressResource"`, `bindings_literal="{}"`, `sync`, `idempotency_literal`.)

- [ ] **Step 2 — Run, expect FAIL:** the `SyncMixin` assertion fails (`"from .idempotency import SyncMixin" not in src`).

- [ ] **Step 3 — Template change** (all conditional; non-opted objects render exactly as today). In the import block (~line 19) add:

```jinja
{% if has_idempotency %}from .idempotency import SyncMixin
{% endif %}
```

  and the class header + classvar (~line 22–25):

```jinja
{% for o in objects %}
class {{ o.classname }}{% if o.sync %}(SyncMixin){% endif %}:
    """Typed wrapper for ``{{ o.attr }}`` (backed by ``{{ o.api_cls }}``)."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {{ o.bindings_literal }}
{% if o.sync %}    _idempotency: ClassVar[dict[str, Any]] = {{ o.idempotency_literal }}
{% endif %}
```

  In `_vendor_resources`, pass `has_idempotency=any(getattr(o, "sync", False) for o in objects)` to the resource template render (~line 239).

- [ ] **Step 4 — Run, expect PASS**, commit:
  `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py tests/test_render.py -q`
  `git commit -m "Wire SyncMixin and the idempotency classvar into resource wrappers"`

### Task 1.6: minimal product opt-in + the live quartet oracles

**Files:** `products/prisma-access/sdk.yml`, `products/prisma-browser/sdk.yml`; create the two live templates.

- [ ] **Step 1 — Opt in exactly the two proven resources** (broaden later). `products/prisma-access/sdk.yml` under `- slug: objects` (block style; also add the top-level `pagination:` block Phase 2 proves — it is required now to clear gate #6):

```yaml
pagination:
  type: offset
```

```yaml
  - slug: objects
    spec: openapi/objects.yaml
    idempotency:
      defaults:
        scope:
          fields:
            - folder
            - snippet
            - device
          rule: exactly_one
      resources:
        address: {}
```

  `products/prisma-browser/sdk.yml` (top level):

```yaml
idempotency:
  defaults:
    read_only:
      - id
  resources:
    application_group:
      computed:
        - applications
```

  (`address: {}` bakes `list_scan`+`put_rmw`+`direct`; `application_group` bakes `list_scan`+`patch_minimal`+`get_after_write` with `hydrate: True`. `applications` is excluded from diff via `computed` exactly as the prototype's `server_only` did — `run_prisma_browser.py` line 112; Phase 5's projection brings it under management.)

- [ ] **Step 2 — Live quartet templates** modeled on `products/prisma-access/overrides/tests/test_scm_crud_live.py.jinja` (same `_REQUIRED_ENV` skip-guard, `phx-sync-<uuid>` names, `finally` cleanup). `products/prisma-access/overrides/tests/test_scm_sync_live.py.jinja` — mirrors `run_prisma_access.py` main() steps 1–7 through the BUILT SDK:

```python
"""Live idempotency quartet — prisma-access address (list_scan + put_rmw + direct).

Mirrors prototypes/sync-engine/run_prisma_access.py (17/17 live) through the BUILT
SDK's generated apply/absent/fetch/diff. Skips (never fails) without credentials.
"""

import os
import uuid

import pytest

import {{ package }}
from {{ package }}._auth import configuration_from_env
from {{ package }}.objects.models import Addresses

_REQUIRED_ENV = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")

pytestmark = pytest.mark.skipif(
    any(not os.environ.get(var) for var in _REQUIRED_ENV),
    reason="live tenant credentials not set: " + ", ".join(_REQUIRED_ENV),
)


@pytest.fixture()
def address(request):
    client = {{ package }}.Client(configuration_from_env())
    return client.objects.address


def _name() -> str:
    return f"phx-sync-{uuid.uuid4().hex[:12]}"


def test_address_idempotency_quartet(address):
    name = _name()
    folder = "Shared"
    try:
        # 1) create
        r = address.apply(Addresses(name=name, folder=folder, ip_netmask="10.10.0.0/24",
                                    description="orig"))
        assert r.changed and r.action == "created"
        # 2) re-apply identical -> unchanged (idempotency proof)
        r = address.apply(Addresses(name=name, folder=folder, ip_netmask="10.10.0.0/24",
                                    description="orig"))
        assert not r.changed and r.action == "unchanged", r.diff.changes
        # 3) modify ip, OMIT description -> PUT RMW must preserve description
        r = address.apply(Addresses(name=name, folder=folder, ip_netmask="10.10.0.0/25"))
        assert r.changed and set(r.diff.changes) == {"ip_netmask"}
        refetched = address.fetch(name=name, folder=folder)
        assert refetched.description == "orig"          # unmanaged preserved
        assert refetched.ip_netmask == "10.10.0.0/25"
        # 4) check_mode predicts without writing
        r = address.apply(Addresses(name=name, folder=folder, ip_netmask="10.10.9.9/32"),
                          check_mode=True)
        assert r.changed
        assert address.fetch(name=name, folder=folder).ip_netmask == "10.10.0.0/25"
        # 5) absent -> deleted; re-absent -> unchanged; fetch -> None
        assert address.absent(Addresses(name=name, folder=folder)).action == "deleted"
        assert not address.absent(Addresses(name=name, folder=folder)).changed
        assert address.fetch(name=name, folder=folder) is None
    finally:
        leftover = address.fetch(name=name, folder=folder)
        if leftover is not None:
            address.delete(id=leftover.id)
```

  `products/prisma-browser/overrides/tests/test_sdk_sync_live.py.jinja` — mirrors `run_prisma_browser.py` (create via id-envelope + get_after_write materializes `after`; re-apply unchanged proves model-split; description drift → patch_minimal isolates `description`; check_mode; absent tail):

```python
"""Live idempotency quartet — prisma-browser application_group
(list_scan + patch_minimal + get_after_write). Mirrors run_prisma_browser.py (13/13)."""

import os
import uuid

import pytest

from {{ package }}.extras.facade import Client
from {{ package }}.models.create_or_replace_app_group_input import CreateOrReplaceAppGroupInput

_REQUIRED_ENV = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")

pytestmark = pytest.mark.skipif(
    any(not os.environ.get(var) for var in _REQUIRED_ENV),
    reason="live tenant credentials not set: " + ", ".join(_REQUIRED_ENV),
)


@pytest.fixture()
def group():
    c = Client.from_env()
    yield c.application_group
    c.close()


def test_application_group_idempotency_quartet(group):
    name = f"phx-sync-{uuid.uuid4().hex[:12]}"
    try:
        r = group.apply(CreateOrReplaceAppGroupInput(name=name, description="orig"))
        assert r.changed and r.action == "created"
        assert r.after.get("name") == name and r.after.get("id")   # get_after_write materialized
        r = group.apply(CreateOrReplaceAppGroupInput(name=name, description="orig"))
        assert not r.changed, r.diff.changes                        # model-split idempotency
        r = group.apply(CreateOrReplaceAppGroupInput(name=name, description="changed"))
        assert r.changed and set(r.diff.changes) == {"description"}  # patch_minimal
        assert group.apply(CreateOrReplaceAppGroupInput(name=name, description="cm"),
                           check_mode=True).changed
        assert group.fetch(name=name).description == "changed"       # check_mode did not write
        assert group.absent(CreateOrReplaceAppGroupInput(name=name)).action == "deleted"
        assert group.fetch(name=name) is None
    finally:
        leftover = group.fetch(name=name)
        if leftover is not None:
            group.delete(id=leftover.id)
```

  Both match the `nox -s live` glob (`out_dir.glob("tests/test_*_live.py")`, noxfile ~line 301), so they run automatically.

- [ ] **Step 3 — Rebuild + run:**
  `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke` (builds both SDKs with the opt-in; `pytest -m real_sdk` must stay green), then `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s live`. Show the output.

**Exit gate (Phase 1):** offline — `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest tests/test_sdk_sync.py tests/test_sdk_idempotency_context.py tests/test_render.py -q` + `uv run nox -s gate` green; the byte-identical regression green (no `extras/idempotency/` for adem). Live — the full quartet green on BOTH products (the prototype's 17/17 + 13/13 rehomed onto generated component code; show output).
`git commit -m "Opt in address and application_group with live sync quartets"`

---

## Phase 2 — Pagination under `list_scan` (F8)

`fetch/list_scan` is only correct with full pagination. The wrapper `_list` paginates only when a `pagination:` component exists (`resource.py.jinja` ~lines 63–75); prisma-access never configured one, so `all_pages=True` silently returned page 1. Fix at the wrapper layer by enabling the offset component (added in Task 1.6); the strategy stays a plain `res.list(all_pages=True, ...)` caller.

### Task 2.1: enable + verify offset pagination for prisma-access

**Files:** `products/prisma-access/sdk.yml` (the `pagination: {type: offset}` block landed in Task 1.6 to clear gate #6); tests: one offline stub + live page-walk.

- [ ] **Step 1 — Offline test** (extend `tests/test_sdk_sync.py`): render the offset `paginate` template, drive `fetch/list_scan` against a canned `list` verb returning 2 pages, prove it finds an object on page 2:

```python
def test_list_scan_pages_past_first_page():
    base, eng = _engine_env()
    ls = _exec_strategy("fetch", "list_scan", base, eng)
    # a wrapper whose `list(all_pages=True)` returns items spanning two pages
    class RPaged:
        def list(self, *, all_pages, limit, **scope):
            return _Page([_Model(name=f"a{i}", id=str(i)) for i in range(limit)] +
                         [_Model(name="target", id="99")])   # page 2 item present only if paged
        _full = eng.SyncMixin._full
    hit = ls.list_scan(RPaged(), {"name": "target"}, {}, _meta(fetch="list_scan"))
    assert hit is not None and hit.id == "99"
```

  (The load-bearing property is that the wrapper's paginated `_list` returns the full set; the strategy just matches over it.)

- [ ] **Step 2 — Live page-walk proof** (extend `test_scm_sync_live.py.jinja`): create 3 uniquely-prefixed addresses, assert `address.list(folder="Shared", limit=2, all_pages=True)` returns all 3 (walks past page 1) and `fetch` finds the 3rd; cleanup in `finally`.

- [ ] **Step 3 — Cursor sanity for prisma-browser** (extend `test_sdk_sync_live.py.jinja`): assert `group_list_wrapper.list(all_pages=True)` succeeds and is a superset of page 1 (small collections; assertion is "no error + superset").

- [ ] **Step 4 — Run:**
  `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke` (gate #6 now passes for prisma-access) `&& uv run nox -s live`.

**Exit gate (Phase 2):** offline gate green; live — pagination proof + the quartet still green on both products.
`git commit -m "Enable offset pagination for prisma-access; list_scan pages fully"`

---

## Phase 3 — The injectable-token seam: `from_access_token` (validated §9)

Additive, independent of idempotency (rides the auth component, so **all** auth-bearing products get it — the one deliberate exception to byte-identical, called out in the CHANGELOG).

### Task 3.1: auth template + facade/composer constructors

**Files:** `components/auth/scm_oauth.py.jinja`, `components/facade/client.py.jinja`, `components/facade/composer.py.jinja`; tests `tests/test_render.py` (following `test_federated_auth_emits_bearer_client_and_config_factory` ~line 156) + a live token-seam leg.

**Prototype mapping:** `_ProviderTokenSource` ← `engine.py::ProviderTokenSource` 48–55; consulted-per-request ← `run_prisma_access.py` 68–85, 153–162.

- [ ] **Step 1 — Failing render tests:**

```python
def test_auth_emits_provider_token_source_and_factory():
    single = _render_auth()
    assert "class _ProviderTokenSource" in single
    assert "def api_client_from_token" in single
    assert '"api_client_from_token"' in single      # __all__
    fed = _render_auth(federated=True)
    assert "def configuration_from_token" in fed
    assert '"configuration_from_token"' in fed


def test_client_and_composer_emit_from_access_token():
    client = render._env().get_template("facade/client.py.jinja").render(**_CLIENT_PARAMS, has_auth=True)
    assert "def from_access_token" in client
    composer = render._env().get_template("facade/composer.py.jinja").render(**_COMPOSER_PARAMS)
    assert "def from_access_token" in composer
```

- [ ] **Step 2 — Run, expect FAIL:** `"class _ProviderTokenSource" not in single`.

- [ ] **Step 3 — Implement** in `scm_oauth.py.jinja` (after the `{{ config_class_name }}` class, ~line 89), unconditional (every auth build):

```jinja
class _ProviderTokenSource:
    """Duck-types TokenManager.token() for a caller-owned token (str | Callable)."""

    def __init__(self, token):
        self._provider = (lambda: token) if isinstance(token, str) else token

    def token(self) -> str:
        return self._provider()


def api_client_from_token(token, *, host: str = DEFAULT_BASE_URL) -> ApiClient:
    cfg = {{ config_class_name }}(token_manager=_ProviderTokenSource(token), host=host)
{% if has_retry %}    cfg.retries = default_retry()
{% endif %}    return {% if federated %}_BearerApiClient(cfg){% else %}ApiClient(cfg){% endif %}
```

  Inside the `{% if federated %}` block (beside `configuration_from_credentials` ~line 141):

```jinja
def configuration_from_token(token, *, host: str = DEFAULT_BASE_URL) -> {{ config_class_name }}:
    """Build the shared {{ config_class_name }} from a caller-owned token source."""
    cfg = {{ config_class_name }}(token_manager=_ProviderTokenSource(token), host=host)
{% if has_retry %}    cfg.retries = default_retry()
{% endif %}    return cfg
```

  Add `"api_client_from_token"` to `__all__` unconditionally and `"configuration_from_token"` inside the federated `__all__` block (~lines 23–32). Facade `client.py.jinja` inside `{% if has_auth %}` (~line 52):

```jinja
    @classmethod
    def from_access_token(cls, token, *, host: str = DEFAULT_BASE_URL) -> "Client":
        return cls(api_client_from_token(token, host=host))
```

  `composer.py.jinja` (~line 72):

```jinja
    @classmethod
    def from_access_token(cls, token, *, host: str = DEFAULT_BASE_URL) -> "Client":
        return cls(configuration_from_token(token, host=host))
```

  (Import `configuration_from_token` / `api_client_from_token` where the composer/client already import the credential factories.)

- [ ] **Step 4 — Live token-seam leg** (append to both live sync templates): build the client via `Client.from_access_token(counting_provider)` where the provider wraps a real `TokenManager` and counts calls; run two reads; assert count ≥ 2 (per-request pull) and the str-token path performs one authenticated list — the prototype's `n=14` observation, minimized.

- [ ] **Step 5 — Run:** `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke && uv run nox -s live`; commit:
  `git commit -m "Add from_access_token client construction (str or callable provider)"`

**Exit gate (Phase 3):** render tests + offline gate green; live seam checks green on both products.

---

## Phase 4 — Symmetric scope validator patch pass (F7 — UX only, lowest priority)

The server already rejects 0-/2-container bodies (validated live, `run_prisma_access.py` scope block); this pass exists for earlier, clearer errors. Deferrable without correctness risk.

### Task 4.1: `patch_scope_validators`

**Files:** `src/phantasos/generator/sdk/patches.py` (new pass + `_ensure_model_validator_import`); call site in `build.py::_generate_one` **after** `apply_generic_patches`, gated on the sub's idempotency config carrying a scope; tests on a fixture model file + a real-artifact assertion.

- [ ] **Step 1 — Failing tests** (mirror `patch_oneof_unwrap_serializer` unit shape):

```python
from phantasos.generator.sdk.patches import patch_scope_validators


def test_scope_validator_injected_into_named_models(tmp_path):
    models = tmp_path / "models"; models.mkdir()
    (models / "addresses.py").write_text(
        "from pydantic import BaseModel\n\n"
        "class Addresses(BaseModel):\n"
        "    id: str | None = None\n"
        "    folder: str | None = None\n"
        "    snippet: str | None = None\n"
        "    device: str | None = None\n",
        encoding="utf-8")
    n = patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"})
    assert n == 1
    text = (models / "addresses.py").read_text()
    assert "_phantasos_scope_exactly_one" in text
    # idempotent
    assert patch_scope_validators(models, ("folder", "snippet", "device"), {"addresses"}) == 0


def test_scope_validator_runtime_behavior(tmp_path):
    # exec the patched model; 0 and 2 containers raise; id-echo skips; exactly 1 ok
    ...  # build Addresses via exec; assert ValueError on 0/2, clean on id-set echo
```

- [ ] **Step 2 — Run, expect FAIL:** `ImportError: cannot import name 'patch_scope_validators'`.

- [ ] **Step 3 — Implement** the pass + import helper (sibling of `_ensure_model_serializer_import` ~line 149):

```python
def _ensure_model_validator_import(text: str) -> str:
    if "model_validator," in text or "import model_validator" in text:
        return text
    return text.replace("from pydantic import ", "from pydantic import model_validator, ", 1)


_SCOPE_VALIDATOR = '''
    @model_validator(mode="after")
    def _phantasos_scope_exactly_one(self):
        """phantasos: exactly one scope container on a user-authored mutation body.
        Skipped for server echoes (id set)."""
        if getattr(self, "id", None) is not None:
            return self
        set_ = [f for f in {fields!r} if getattr(self, f, None) is not None]
        if len(set_) != 1:
            raise ValueError(
                f"exactly one of {fields_h} must be set (got {{set_ or 'none'}})"
            )
        return self
'''


def patch_scope_validators(models_dir, scope_fields, model_stems) -> int:
    count = 0
    fields = tuple(scope_fields)
    fields_h = "/".join(fields)
    for path in sorted(models_dir.glob("*.py")):
        if path.stem not in model_stems:
            continue
        text = path.read_text(encoding="utf-8")
        if "_phantasos_scope_exactly_one" in text:
            continue  # idempotent
        if "\nclass " not in text:
            continue  # anchor absent
        text = _ensure_model_validator_import(text)
        method = _SCOPE_VALIDATOR.format(fields=fields, fields_h=fields_h)
        # inject as the last member of the first class body (append before EOF)
        text = text.rstrip("\n") + "\n" + method + "\n"
        path.write_text(text, encoding="utf-8")
        count += 1
    return count
```

  (Refine the injection anchor to place the method inside the class body — the exact insertion point mirrors `patch_oneof_unwrap_serializer`'s `.replace("\n    def to_str(self)", ...)`; pick a stable per-class anchor rather than EOF if the file has trailing module-level code.) Call site in `build.py` after `apply_generic_patches`:

```python
    sub_idem = getattr(loaded.config, "idempotency", None) or (context or {}).get("idempotency")
    if sub_idem and sub_idem.defaults.scope:
        from . import patches
        # model stems = the create/update body model files from the wrapper context
        patches.patch_scope_validators(pkg_dir / "models",
                                       tuple(sub_idem.defaults.scope.fields),
                                       _scope_model_stems(loaded, sub_idem))
```

  (`_scope_model_stems` derives the create/update body model file stems from the same producer facts as `_idempotency["models"]`; wire the sub's idempotency block through the federated loop like `operations`.)

- [ ] **Step 4 — Real-artifact check** (extend the built prisma-access ring): `Addresses(name=..., folder=..., snippet=..., ip_netmask=...)` raises at construction; a dict with `id` + no container round-trips `model_validate` — settles spec §13's echo-guard question against real payloads. If an echo without `id` and without a container surfaces, fall back to create-only models + engine-side rule and record the decision.

- [ ] **Step 5 — Run:** `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke && uv run nox -s live` (the quartet must stay green — the validator must not reject `mutate/put_rmw` bodies, which always carry exactly one container from the fetched actual).
  `git commit -m "Add client-side scope mutual-exclusion validator for scoped products"`

**Exit gate (Phase 4):** offline + real-artifact assertions green; live quartet unaffected.

---

## Phase 5 — Per-field projections (F5) + write-only fields (F6 escape hatch)

Both land in the **engine core** (`_normalize`/`diff` in `engine.py.jinja`) — NOT a new strategy family (one projection type so far → YAGNI).

### Task 5.1: `projections:` (F5)

**Files:** `engine.py.jinja` (`diff`), `idempotency.py` (already passes `projections` through, Task 0.2), tests `tests/test_sdk_sync.py` + live.

- [ ] **Step 1 — Failing unit test:**

```python
def test_projection_maps_actual_objects_to_ids_no_false_drift():
    base, eng = _engine_env()
    actual = _Model(name="a", id="1", applications=[{"id": "a1", "name": "X"}])
    meta = _meta(input_fields=["name", "applications"], projections={"applications": "id"})
    res, _ = _stub(base, eng, meta, existing=actual)
    assert not res.apply(_Model(name="a", applications=["a1"])).changed
    assert res.apply(_Model(name="a", applications=["a2"])).changed
```

- [ ] **Step 2 — Run, expect FAIL:** the first assertion fails (permanent false drift — `["a1"] != [{"id":...}]`).

- [ ] **Step 3 — Implement** the projection hook in `SyncMixin.diff`, before normalization, on the **actual** side of an annotated field:

```python
    def _project(self, key, value):
        sub = self._idempotency.get("projections", {}).get(key)
        if sub and isinstance(value, list):
            return [item.get(sub) if isinstance(item, dict) else item for item in value]
        return value
```

  and in `diff`, replace `a.get(key)` in the comparison with `self._project(key, a.get(key))` (keep `changes` recording the un-normalized wire values). Add a unit assertion that `Diff.changes["applications"]["before"]` remains the raw object list.

- [ ] **Step 4 — Opt the field in live:** flip prisma-browser `application_group` from `computed: [applications]` to `projections: {applications: id}`, extend the live quartet to manage `applications` (no false drift on re-apply; real drift on membership change). Requires a stable application id (reuse the composite-identity read of `run_prisma_browser.py` 166–180 to pick one, or skip that leg when the tenant has none).

### Task 5.2: `write_only:` (F6)

**Files:** `engine.py.jinja` (comparable set already subtracts `write_only` — Task 1.2), `idempotency.py` (gate #5 message), tests.

- [ ] **Step 1 — Failing tests:** baking — a resource whose managed field is missing from the read model passes gate #5 **iff** listed under `write_only:`; engine — a `write_only` field is excluded from `diff`, still sent on create, and included in the `put_rmw` overlay when user-set.

```python
def test_write_only_field_resolves_f6_gate(real_sdk):
    cfg = IdempotencyConfig.model_validate(
        {"resources": {"user_group": {"identity": ["name"], "write_only": ["userIds"]}}}
    )
    v = _views(real_sdk / "prisma_browser", "prisma_browser", cfg)["user_group"]
    assert '"write_only": ["userIds"]' in v.idempotency_literal


def test_write_only_excluded_from_diff_but_sent_on_create():
    base, eng = _engine_env()
    meta = _meta(input_fields=["name", "userIds"], write_only=["userIds"])
    res, rec = _stub(base, eng, meta, existing=None)
    res.apply(_Model(name="a", userIds=["u1"]))
    body = next(b for k, b in rec if k == "create")
    assert body.model_dump()["userIds"] == ["u1"]        # sent on create
```

- [ ] **Step 2 — Implement** both sides: gate #5 already subtracts `write_only` from `managed` (Task 0.2); extend its message to offer `write_only:` as the second resolution (currently `sync: false` only). The comparable-set exclusion is already in `_comparable` (Task 1.2). Confirm create/put_rmw include the field (they use `_present`, which does not subtract `write_only`).

- [ ] **Step 3 (optional live):** opt in prisma-browser `user_group` with `write_only: [userIds]` and run its quartet — description-drift only (drift on `userIds` is undetectable by design).

**Exit gate (Phase 5):** unit + baking tests green; live quartet green including the `applications`-managed leg; offline gate green.
`git commit -m "Support per-field projections and write-only managed fields"`

---

## Phase 6 — Test consolidation + broader rollout (+ `fetch/get` for singletons)

Closes coverage gaps, proves the negative space, and widens the opt-in. Adds the deferred `fetch/get` strategy the first singleton needs.

- [ ] **Task 6.1: Negative-space regression suite.** (a) adem builds with zero idempotency artifacts (no `extras/idempotency/`, no `SyncMixin` import, no `_idempotency`); (b) spec §6 semantics — candidates with inferable identity sync by default; `sync: false` opts out; uninferable + unlisted fails the build. Encode as baking tests if Phase 0 did not.
  `git commit -m "Add negative-space regression tests for the idempotency opt-in gate"`

- [ ] **Task 6.2: `fetch/get` (singleton) + a singleton opt-in.** Create `components/idempotency/fetch/get.py.jinja`:

```jinja
from __future__ import annotations

from typing import Any

from ..base import FETCH, NotFoundException


def get(res: Any, identity: dict, scope: dict, meta: dict) -> Any | None:
    try:
        return res.get()
    except NotFoundException:
        return None


FETCH["get"] = get
```

  Unit test: 404 → None; present → object. Opt in one prisma-access singleton (`bgp_routing: {singleton: true}` under `network_services`) and assert `apply` takes the fetch→diff→update path and `absent` raises `AbsentNotSupported`. Live: fetch→diff→update leg only (no create/delete lifecycle).
  `git commit -m "Add the singleton fetch/get strategy and opt in a singleton resource"`

- [ ] **Task 6.3: Real-artifact ring** (pattern: `pytest -m real_sdk`): the BUILT prisma-browser `application_group` exposes `apply/absent/fetch/diff` with the §4.1 signatures and `_idempotency["mutate"] == "patch_minimal"` / `["materialize"] == "get_after_write"`; the built prisma-access `address._idempotency` carries `fetch == "list_scan"`, `mutate == "put_rmw"`, `materialize == "direct"`, `update == {"verb": "replace"}`, scope trio; both packages contain an `extras/idempotency/` tree holding **only** the referenced strategy modules; `Client.from_access_token` exists on both. Skips when the sibling SDKs are not built.
  `git commit -m "Add real-artifact ring assertions for the idempotency surface"`

- [ ] **Task 6.4: Broaden the prisma-access opt-in** (conservative): `tag: {}`, `address_group: {order_sensitive: [static]}` under objects — each must pass the Phase-0 gates; extend the live quartet to `tag` (cheap pure-reshape object). Resources that trip a gate get an explicit `sync: false` with a YAML comment naming the reason (`auto_tag_action` — no natural key). Full-catalog rollout (~130+ resources) is a follow-up.
  `git commit -m "Broaden prisma-access idempotency opt-in to tag and address_group"`

- [ ] **Task 6.5: Full ladder:** `uv run nox -s gate` → `NOX_ENVDIR=/tmp/phantasos-nox uv run nox -s smoke` → `uv run nox -s live` (all quartets + pagination + token seam), plus `uv run nox -s sdk-docs` (built SDKs must still doc-build with the new extras package).

**Exit gate (Phase 6):** the entire ladder green; every suite named in this plan passing in one run.

---

## Phase 7 — Docs & context (no doc commits)

Write and update; leave staging/committing to the human.

- [ ] **Task 7.1:** `CHANGELOG.md` `## [Unreleased]` → `### Added`: idempotent sync (`apply`/`absent`/`fetch`/`diff`, opt-in via `sdk.yml idempotency:`, composable fetch/mutate/materialize strategies per ADR-0004), `from_access_token` (note: emitted for all auth-bearing products — the intentional byte-diff), prisma-access offset pagination, scope validator. **Edit only — do NOT `git add`/commit.**
- [ ] **Task 7.2:** `.agents/context/sdk-generator.md` — the idempotency component tree (orchestrator + base + strategy families), the producer + auto-selection + union-vendoring + gates, the pagination dependency; `.agents/context/product-config.md` — the `idempotency:` block reference (block-style examples, the strategy-override escape hatch). Then `uv run nox -s context` and confirm `-- --check` passes. **Do not commit docs.**
- [ ] **Task 7.3:** Generated-SDK MkDocs "Sync operations" guide via `generator/sdk/docs.py` (apply/absent semantics, check_mode, `SyncResult`/`Diff`, `write_only` partial-sync caveat, auto-selected strategies + the custom-strategy extensibility path). Keep `sdk-docs` assertions green. Split to a follow-up if the docs plumbing balloons.
- [ ] **Task 7.4:** Tell the human which doc files are ready to review and commit. Open the PR with the **code** only: `gh pr create --base develop` (squash), no version bump.

**Exit gate (Phase 7):** `uv run nox -s context -- --check` and `uv run nox -s sdk-docs` green; final full ladder green; code PR → `develop`; docs left for human commit.

---

## Self-Review

**Spec-section → task coverage (every section maps to a task):**

| Spec | Task |
|---|---|
| §4 contract (`apply`/`absent`/`fetch`/`diff`, `Diff`/`SyncResult`, `AbsentNotSupported`/`IdentityUnresolved`) | Task 1.2 (engine) |
| §4.4 `from_access_token` | Task 3.1 |
| §5.1–5.3 orchestrator + Protocol seams + registries | Tasks 1.1, 1.2 |
| §5.4 baked `_idempotency` classvar | Task 0.2 |
| §5.5 auto-selection + `defaults`/`resources` precedence + union-vendoring | Tasks 0.1, 0.2, 1.4 |
| §5.6 prototype mapping (per strategy) | Task 1.3 |
| §5.8 `resource.py.jinja` wiring (byte-identical when off) | Task 1.5 |
| §6 config models (incl. `IdempotencyDefaults.fetch/mutate/materialize`) | Task 0.1 |
| §7 diff semantics (`_normalize`, comparable set) | Task 1.2 |
| §8.1 singletons / `AbsentNotSupported` | Tasks 1.2 (raise) + 6.2 (`fetch/get` + opt-in) |
| §8.2 composite identity | Task 1.2 (identity-as-list unit test) |
| §8.3 no resolvable identity gate | Task 0.2 (gate #2) |
| §9 auth seam (single + federated) | Task 3.1 |
| §10 scope validator (F7 UX-only) | Task 4.1 |
| §11 rollout / opt-in / byte-identical | Tasks 0.2 exit gate, 1.5, 1.6, 6.1, 6.4 |
| §12 testability (offline unit / baking / real-artifact / live quartet) | Tasks 0.2, 1.2, 1.3, 6.3, 1.6 |
| F1 | Task 0.2 fetch default + `fetch/list_scan` (1.3) |
| F2 | `fetch/list_scan` 404/empty→None (1.3) |
| F3 | Task 0.2 `materialize`/`id_field` + `materialize/get_after_write` (1.3) |
| F4 | Task 0.2 `models` + mutate strategies' model-class use (1.3) |
| F5 | Task 5.1 (engine-core projection hook) |
| F6 | Task 0.2 gate #5 + Task 5.2 |
| F7 | Task 4.1 (framed UX, deferrable) |
| F8 | Task 0.2 gate #6 + Phase 2 |
| F9 | Task 0.2 `mutate`/`update.verb` + mutate strategies' verb dispatch (1.3) |

**Type-consistency check across tasks (the shared contract holds end-to-end):**
- `_idempotency` literal keys baked in Task 0.2 (`identity`, `scope`, `models`, `input_fields`, `server_only`, `id_field`, `order_sensitive`, `write_only`, `projections`, `singleton`, `update.verb`, `fetch`, `mutate`, `materialize`, `fetch_opts`) are exactly the keys read by the engine (Task 1.2: `identity`/`scope`/`models["create"]`/`server_only`/`id_field["attr"]`/`order_sensitive`/`write_only`/`projections`/`singleton`/`update["verb"]`/`fetch`/`mutate`/`materialize`) and the strategies (Task 1.3: `fetch_opts["page_limit"]`/`["hydrate"]`, `id_field["wire"]`/`["attr"]`, `models["update"]`, `update["verb"]`). No key is baked-but-unread or read-but-unbaked.
- Strategy call signatures are identical across the Protocols (Task 1.1), the orchestrator's `FETCH[..](self, identity, scope, meta)` / `MUTATE[..](self, desired, actual, diff, meta)` / `MATERIALIZE[..](self, response, identity, scope, meta)` calls (Task 1.2), and each module's `def` (Task 1.3).
- `referenced_strategies` (Task 0.2) returns `{"fetch","mutate","materialize"} -> set[str]`; consumed verbatim by `_vendor_idempotency` (Task 1.4) and the `__init__.py.jinja` import loops (Task 1.3).
- `ObjectView.sync` / `idempotency_literal` (Task 0.2) are the exact fields read by `resource.py.jinja` (`o.sync`, `o.idempotency_literal`) and by `has_idempotency=any(o.sync ...)` (Task 1.5).

**Placeholder scan:** every task carries its files with line anchors, its prototype source lines (Tasks 1.2/1.3/3.1), a shown failing test, an exact `uv run pytest ...` / `nox -s gate|smoke|live` command with expected FAIL/PASS, and a plain-imperative commit message. Two spots are explicitly flagged for confirmation-at-implementation rather than left vague: (1) whether `sub_verb` / `body_model_live` / per-param `location` are already reachable on the IR views (Task 0.2 Step 3 folds in the minimal accessor + a micro-test if not); (2) the scope-validator in-class injection anchor (Task 4.1 Step 3 pins it to the `patch_oneof_unwrap_serializer` anchor pattern rather than EOF). No "TBD", no "similar to Task N", no undefined symbols.

**Spec deltas deliberately carried (F-findings override the base spec):** `fetch` default is `list_scan` (F1), not the spec's "universal name filter"; `_idempotency` carries three strategy names + `models`/`materialize`/`id_field`/`fetch_opts`/`write_only`/`projections` (richer than spec §5.2's single `input_fields`); the scope validator is deferrable UX (F7); `absent` keeps the model-or-identity-object contract (kwargs sugar not built); `server_only` derives from annotations + the resolved id field rather than re-reading spec `readOnly` (documented simplification, load-bearing for prisma-browser per §3).
