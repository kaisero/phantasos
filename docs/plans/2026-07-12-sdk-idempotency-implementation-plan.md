# SDK Idempotent Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every opted-in resource of a generated SDK gains a first-class, tested idempotent sync surface — `apply` / `absent` / `fetch` / `diff` — plus the injectable-token client constructor `from_access_token`, so a later Ansible-collection target (and CLI `apply`) consume one shared, generator-baked engine instead of per-consumer orchestration.

**Architecture (per ADR-0004):** A new SDK component **tree** `components/idempotency/` vendored under `<pkg>/extras/idempotency/` — a thin **orchestrator** (`engine.py.jinja` → `SyncMixin` + `Diff`/`SyncResult` + two exceptions), the **seam contracts + registries** (`base.py.jinja` → the `FetchStrategy`/`MutateStrategy`/`MaterializeStrategy` Protocols and the `FETCH`/`MUTATE`/`MATERIALIZE` dicts), and three families of small **strategy modules** (`fetch/{list_scan,list_filter,get}`, `mutate/{put_rmw,patch_minimal}`, `materialize/{direct,get_after_write}`). A per-resource `_idempotency` classvar — baked by `build_wrapper_context` from a new `sdk.yml` `idempotency:` block + the IR + live model introspection — names the three strategies (auto-derived) plus the data they read. `render.vendor()` writes `engine.py` + `base.py` and **only the union** of strategy modules the opted-in resources reference. Plus: a pagination enablement for prisma-access (offset, because `list_scan` is load-bearing), an additive `from_access_token` seam on the auth component, and a low-priority scope-validator patch pass. Everything is opt-in: a product without an `idempotency:` block regenerates byte-identically (the only exception is `from_access_token`, which rides the auth component — see Phase 3).

**Tech Stack:** Python 3.11+, Jinja2 component templates (`src/phantasos/generator/sdk/components/`), pydantic v2 config models, the opmodel IR (`generator/opmodel/`), pytest, nox (`gate`/`smoke`/`live`).

**Spec:** `docs/specs/2026-07-12-sdk-idempotency-for-ansible-design.md` — **§0 Validation findings F1–F9 are authoritative** where they contradict later sections; **§5 (rev. per ADR-0004) is the component decomposition this plan builds.** **ADRs:** 0002 (sync is an SDK operation), 0003 (metadata lives in `sdk.yml`), **0004 (idempotency strategies are composable per-resource components).** **Empirical ground truth:** `prototypes/sync-engine/` — `engine.py` (the generic engine), `run_prisma_access.py` (17/17 live), `run_prisma_browser.py` (13/13 live), `NOTES.md`. The engine/strategy tasks below carry explicit **"prototype mapping"** notes; translate that code, don't reinvent it.

## Divergence from the prior plan (ADR-0004)

The previous revision of this plan built a **monolithic** `SyncMixin` (one `sync.py.jinja` → `extras/sync.py`) with inline `if meta["fetch"]["strategy"] == …` / `if meta["update"]["strategy"] == "patch"` branches. **ADR-0004 supersedes that**: fetch, mutate, and materialize each already have 2+ real variants proven live across the two products, so by the "two adapters make a real seam" rule they are real seams. This plan therefore builds a thin orchestrator + named strategy modules selected per resource, vendored as the union the product references. Net effect on this plan: Phase 0's producer now **auto-selects three strategy names + computes the union to vendor**; Phase 1 becomes "orchestrator + base protocols/registry + the strategy modules the two proven resources need"; every prototype-mapping table is now **per strategy module** (each independently unit-tested). All exit gates, the byte-identical/opt-in guarantee, effort sizing, and the live quartet are unchanged.

## Validated realities this plan builds on (non-negotiable)

These corrections from §0/`NOTES.md` supersede the original spec text wherever they conflict; each now lands **inside a specific strategy**:

| # | Finding | Consequence in this plan |
|---|---|---|
| F1 | SCM `name=` list filter is non-functional | fetch **defaults to the `list_scan` strategy**; `list_filter` is per-resource opt-in, validated against the list binding's query params (Phase 0/1) |
| F2 | Absence surfaces as 404 **or** empty list | fetch/`list_scan` absorbs both `NotFoundException` and empty match sets → `None` (Phase 1) |
| F3 | Mutation responses are often id-only envelopes | metadata bakes `materialize: "get_after_write"` + `id_field`; the materialize strategy GETs by id after create/update (Phases 0–1) |
| F4 | create/patch/put/read are different model classes (prisma-browser) | metadata carries **per-operation model classes** (`models.{create,update,read}`), not one `input_fields` source (Phase 0); the orchestrator + strategies map desired → the right model (Phase 1) |
| F5 | Same field, different request/response shape (`list[str]` vs `list[obj]`) | per-field `projections:` annotation + a hook in the engine-core `_normalize` (Phase 5) — NOT a strategy family (YAGNI) |
| F6 | Write-only managed fields (set on create, never echoed by GET) | **build-time gate** in the metadata producer: fail loudly, resolve via `sync: false` or the `write_only:` annotation (Phases 0 and 5) |
| F7 | The server already rejects 0-/2-container bodies | the symmetric scope validator is **fail-fast UX**, not correctness — generated, but lowest priority (Phase 4) |
| F8 | The built `_list` returns the first page only for prisma-access (no `pagination:` component) | pagination is now **load-bearing** for `list_scan`; fix = enable the existing offset component for prisma-access + a build gate (Phase 2) |
| F9 | The update verb is `replace` (PUT) or `update` (PATCH) | metadata bakes `mutate: "put_rmw" | "patch_minimal"` + `update.verb`; the mutate strategy calls the named verb (Phases 0–1) |

Confirmed-good and kept as validated: `apply`/`absent` quartet semantics, typed `Diff`/`SyncResult`, PUT read-modify-write preserving unmanaged fields, PATCH-minimal, `check_mode` without writes, `from_access_token(str | Callable)` consulted per request, alias-aware `by_alias` diff, scope excluded-from-diff / carried-from-actual.

## Global Constraints

- **Branch:** `feature/sdk-idempotent-sync` off `develop`; PR → `develop` (`gh pr create --base develop`), squash-merge, **no version bump**, record under `## [Unreleased]` in `CHANGELOG.md`.
- **Run tests with:** `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sync uv run pytest ...` (repo may sit on sshfs). Offline gate: `uv run nox -s gate`. SDK rebuilds: `uv run nox -s smoke` (with `NOX_ENVDIR=/tmp/phantasos-nox` where venv-backed).
- **Phase boundaries:** run `uv run nox -s live` (skips without credentials) before declaring a phase complete. From Phase 1 on, "live" includes the **idempotency quartet** (create→changed, re-apply→unchanged, modify→changed with correct diff, absent→changed) on prisma-access `address` and prisma-browser `application_group` — both proven live by the prototype.
- **Byte-identical rule:** every template change that is idempotency-conditional must be guarded so a product without an `idempotency:` block renders `resources.py`/`facade.py`/extras exactly as today — **no `extras/idempotency/` directory at all**. `adem` (never opted in) is the regression canary.
- **Test policy:** never mock the system under test or the prisma-browser API boundary. Engine/strategy unit tests drive the real rendered orchestrator + strategy callables against a stub resource carrying a hand-built `_idempotency` classvar + canned wrapper verbs — scaffolding around the real SUT, not an API mock.
- **YAML style:** `products/*/sdk.yml` additions are block style only; empty mappings stay flow (`address: {}`).
- **Docs are the human's to commit:** this plan and all Markdown it touches are written but never `git add`ed by the implementer.
- **Prototype is throwaway:** `prototypes/sync-engine/` is read-only reference. Do not import from it; do not ship it.

## File Structure

**Create — the component tree** (`src/phantasos/generator/sdk/components/idempotency/`; vendored under `<pkg>/extras/idempotency/`):
- `base.py.jinja` — the `FetchStrategy` / `MutateStrategy` / `MaterializeStrategy` `Protocol`s and the `FETCH` / `MUTATE` / `MATERIALIZE` registry dicts. ~static; the only conditional is the `NotFoundException` import split (federated vs single-spec).
- `engine.py.jinja` — the orchestrator `SyncMixin` (uniform steps: identity/scope extraction, the desired-subset diff + `_normalize` projection hook, create-body construction, `check_mode`, `SyncResult` assembly) + `Diff` / `SyncResult` + `AbsentNotSupported` / `IdentityUnresolved`. Resolves strategies through the `base.py` registries.
- `fetch/list_scan.py.jinja`, `fetch/list_filter.py.jinja`, `fetch/get.py.jinja` — the fetch family; each registers its callable in `FETCH`.
- `mutate/put_rmw.py.jinja`, `mutate/patch_minimal.py.jinja` — the mutate family; each registers in `MUTATE`.
- `materialize/direct.py.jinja`, `materialize/get_after_write.py.jinja` — the materialize family; each registers in `MATERIALIZE`.
- `__init__.py.jinja` (vendored as `extras/idempotency/__init__.py`) — re-exports `SyncMixin`, `Diff`, `SyncResult`, the two exceptions; imports the union of vendored strategy modules so their registrations run at import time.

**Create — producer + tests:**
- `src/phantasos/generator/sdk/idempotency.py` — the metadata producer (`resolve_idempotency`, `_idempotency_literal`, `select_strategies`, `referenced_strategies`, the F6/F8 build gates). Kept out of `wrapper.py` (811 lines already); `build_wrapper_context` calls into it.
- `tests/test_sdk_idempotency_context.py` — baking tests for the producer, strategy selection, union computation, and gates.
- `tests/test_sdk_sync.py` — orchestrator + per-strategy unit tests against the rendered templates.
- `products/prisma-access/overrides/tests/test_scm_sync_live.py.jinja` — live quartet, prisma-access `address`.
- `products/prisma-browser/overrides/tests/test_sdk_sync_live.py.jinja` — live quartet, prisma-browser `application_group`.

**Modify:**
- `src/phantasos/config.py` — `ScopeSpec`, `IdempotencyResource` (incl. `fetch`/`mutate`/`materialize` strategy-override fields + `page_limit`/`hydrate`), `IdempotencyDefaults`, `IdempotencyConfig` (after `OperationOverride`, ~line 150).
- `src/phantasos/productconfig.py` — `SubPackage.idempotency` (~line 117), `ProductConfig.idempotency` (~line 161) + placement validator.
- `src/phantasos/generator/sdk/wrapper.py` — `ObjectView` gains `sync: bool = False` / `idempotency_literal: str = "{}"` (~line 169); `build_wrapper_context` (~line 716) gains `idempotency=` and calls the producer after `_bindings_literal` (~line 810).
- `src/phantasos/generator/sdk/render.py` — `vendor()` (~line 46) threads `idempotency=`; writes `extras/idempotency/{engine,base,__init__}.py` + the **union** of referenced strategy modules (a new `_vendor_idempotency` helper writing the tree, mirroring `write_component`); `_vendor_resources` (~line 202) passes `has_idempotency` to the template.
- `src/phantasos/generator/sdk/build.py` — `_generate_one` (~line 103) passes the per-sub / top-level idempotency block (mirroring `operations=`).
- `src/phantasos/generator/sdk/components/facade/resource.py.jinja` — conditional `from .idempotency import SyncMixin`, `SyncMixin` base + `_idempotency` classvar beside `_bindings` (line 25).
- `src/phantasos/generator/sdk/components/auth/scm_oauth.py.jinja` — `_ProviderTokenSource`, `api_client_from_token`, federated `configuration_from_token`, `__all__`.
- `src/phantasos/generator/sdk/components/facade/client.py.jinja` + `composer.py.jinja` — `from_access_token` classmethods.
- `src/phantasos/generator/sdk/patches.py` — `patch_scope_validators` (new pass, sibling of `patch_oneof_unwrap_serializer`).
- `products/prisma-access/sdk.yml` — `pagination:` block + per-sub `idempotency:` opt-in.
- `products/prisma-browser/sdk.yml` — `idempotency:` opt-in.
- `CHANGELOG.md`, `.agents/context/sdk-generator.md`, `.agents/context/product-config.md` (Phase 7).

---

## Phase 0 — Metadata model: `sdk.yml` config, the `_idempotency` producer (auto-select + union), build gates

The foundation everything else interprets. No runtime behavior yet — this phase ends with the generator baking a correct, gate-checked `_idempotency` literal into `ObjectView` (including the three auto-selected **strategy names** and the F4/F3/F1 facts), plus computing the **union of strategy modules to vendor**.

**Effort:** M–L (~2–3 days). **Risk:** highest-leverage phase; the literal's shape + the strategy names are the engine's contract — get it reviewed before Phase 1 starts.

### Task 0.1: `sdk.yml` config models

**Files:** `src/phantasos/config.py` (after `OperationOverride`), `src/phantasos/productconfig.py`, `tests/test_config.py` / `tests/test_productconfig.py`.

- [ ] **Step 1: Failing tests** — `IdempotencyConfig` round-trips the spec §6.2/§6.3 examples; unknown keys rejected (`extra="forbid"`); federated product with a **top-level** `idempotency:` fails validation ("declare it per sub-package"); a resource entry may carry an explicit `fetch: list_filter` / `mutate: patch_minimal` strategy override (accepted, round-trips); unknown strategy name string accepted at config-load (validated later against the vendored set at build — a custom module path is legal).
- [ ] **Step 2: Models** in `config.py`:

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
    # Strategy overrides — ESCAPE HATCH, not routine (ADR-0004 / spec §5.5).
    # Each family is auto-selected + baked by the producer; set one only to force
    # a non-default variant or name a custom module (`type: ./path.jinja`/hooks.py).
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
    # this idempotency block unless a `resources.<name>` entry overrides them. Left
    # UNSET means "use the producer's auto-selection" (the chosen default today).
    # Precedence per family: resources.<name>.<family>  >  defaults.<family>  >  auto.
    fetch: str | None = None                # e.g. whole API's name filter works -> "list_filter"
    mutate: str | None = None
    materialize: str | None = None


class IdempotencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    defaults: IdempotencyDefaults = Field(default_factory=IdempotencyDefaults)
    resources: dict[str, IdempotencyResource] = Field(default_factory=dict)
```

- [ ] **Step 3: Wire through `productconfig.py`** — `SubPackage.idempotency: IdempotencyConfig | None = None` and `ProductConfig.idempotency: IdempotencyConfig | None = None`; extend `_exactly_one_spec_mode` (or a sibling validator): federated + top-level `idempotency` → `ValueError` (same split as `operations:`).
- [ ] **Step 4:** tests green; commit (`Add sdk.yml idempotency config models`).

### Task 0.2: the `_idempotency` literal producer — strategy auto-selection, union, build gates

**Files:** create `src/phantasos/generator/sdk/idempotency.py`; modify `wrapper.py` (`ObjectView` ~169, `build_wrapper_context` ~716); test `tests/test_sdk_idempotency_context.py`.

The producer runs inside `build_wrapper_context` **after** methods are assembled and `bindings_literal` is computed (~line 810) — it needs the final `MethodView` set (verbs, bindings, return models) plus live model classes. Signatures:

```python
def resolve_idempotency(
    objects: list[ObjectView],
    cfg: IdempotencyConfig,
    package: str,                 # live-import model classes, alias-aware
    *,
    has_pagination: bool,
) -> None:
    """Mutates each opted-in ObjectView: sync=True, idempotency_literal=...,
    imports |= {model imports the literal references}. Raises ValueError on
    every gate below (fail-loud, listing resource + resolution)."""


def referenced_strategies(objects: list[ObjectView]) -> dict[str, set[str]]:
    """After resolve_idempotency: the UNION per family, e.g.
    {"fetch": {"list_scan"}, "mutate": {"put_rmw"}, "materialize": {"direct"}}.
    render.vendor() writes exactly these modules."""
```

**Strategy auto-selection** (each has a baking test; overridable by the `sdk.yml` fields from Task 0.1):

| Family | Baked name | Derivation | Finding |
|---|---|---|---|
| `fetch` | `"list_scan"` (default) | safe default; `"list_filter"` only when the resource sets `fetch: list_filter` AND every identity field is a query param on the list binding (`ParamInfo.location == "query"`) — else **gate**. `"get"` when `singleton: true` | F1 |
| `mutate` | `"put_rmw"` / `"patch_minimal"` | `"patch_minimal"` when an `update` method exists whose bindings classify as sub-verb `patch`; else `"put_rmw"` when a `replace` method exists; neither → **gate** ("no update verb — set `sync: false`") | F9 |
| `materialize` | `"direct"` / `"get_after_write"` | `"direct"` when the mutating verb's `return_model` equals the read model name; else `"get_after_write"` (id-only envelope) | F3 |

**Selection precedence** (per family, resolved by the producer): `resources.<name>.<family>` → `defaults.<family>` → auto-derived above. An explicit string at either level overrides the derived value verbatim (custom module names / `./path.jinja` pass through — validated against the vendored union at render time, not here). The `list_filter` query-param gate (row `fetch`) fires wherever the resolved value is `list_filter`, whether it came from a resource entry or a product/subpackage `defaults.fetch`. **For now both products leave `defaults` strategy fields unset — every resource uses auto-selection**; the fields exist so a future product can set a blanket default without annotating each resource, still overridable per resource.

**Data the strategies read** (baked alongside the names):

| Metadata key | Derivation | Finding |
|---|---|---|
| `identity` | annotation, else infer `["name"]` when the **create-input model** has a `name` wire key; neither → **gate**: "needs `identity:` or `sync: false`" (mirrors the anchorless-op gate, `wrapper.py` ~229) | — |
| `scope` | per-resource override, else `defaults.scope`, else `None` (all scope steps no-op) | — |
| `models` | **unquoted class identifiers** for `create` / `update` / `read`: create = the create binding's live body model (`_build_method` resolves `body_model_live`, ~line 554); update = the `update` (PATCH) or `replace` (PUT) binding's body model; read = the `get` verb's return model (fallback: the list item model). Producer adds their `(module, class)` pairs to `ObjectView.imports` so `resources.py` imports them | F4 |
| `input_fields` | union of create+update model **wire keys** — from the live classes: `f.alias or name` per `model_fields` (NOT `FieldInfo.name`, the python name) | F4 |
| `server_only` | resolved `id_field` ∪ `defaults.read_only/computed` ∪ per-resource `read_only/computed` | — |
| `id_field` | `{"wire": ..., "attr": ...}` for `id` on the read model; **gate** if a `get_after_write` materialize has no resolvable id | F3 |
| `update.verb` | the wrapper verb name of the update binding (`replace` / `update`) — the mutate strategy calls `getattr(self, meta["update"]["verb"])` | F9 |
| `fetch_opts` | `{"page_limit": N, "hydrate": bool}`; `hydrate` auto-True when a `get` verb exists (list items may be partial — the browser prototype GETs after match), overridable | F1 |
| `order_sensitive`, `singleton`, `write_only`, `projections` | verbatim from the resource entry (engine support for the last two lands in Phase 5) | F5/F6 |

**Build gates** (all `ValueError`, all listing the resource and the fix):

1. **Unknown `resources:` keys** — validated against the built object attrs (same posture as `validate_override_keys`, `wrapper.py` ~57).
2. **Unresolvable identity** (above).
3. **`list_filter` without query params** — resource forces `fetch: list_filter` but an identity field is not a list query param → error naming the field.
4. **No update verb** — neither a `patch` nor a `replace` binding, and `sync: true` → error ("set `sync: false`").
5. **F6 write-only gate:** `managed = input_fields − server_only − scope − write_only`; any managed field whose wire key is absent from the **read model** → error: "field(s) X undetectable via GET on <resource>; declare `write_only:` (partial sync) or `sync: false`". (Until Phase 5 ships `write_only` engine support, the message offers `sync: false` only.)
6. **F8 pagination gate:** any opted-in resource whose baked `fetch == "list_scan"` while the product has no `pagination:` component → error: "list_scan fetch requires a pagination component (sdk.yml `pagination:`)". Makes Phase 2 impossible to forget.
7. **Singleton sanity:** `singleton: true` with a create or delete binding present → error (config lies about lifecycle).

- [ ] **Step 1: Failing baking tests** in `tests/test_sdk_idempotency_context.py`, following `tests/test_sdk_wrapper.py`'s stub-inventory pattern: (a) the three strategy names for a CRUD-complete PUT object (`fetch=list_scan`, `mutate=put_rmw`, `materialize=direct`) and a PATCH/id-envelope object (`fetch=list_scan` default, `mutate=patch_minimal`, `materialize=get_after_write`); (b) `fetch: list_filter` override accepted when identity is a query param, gated otherwise; (c) full literal contents (identity inference, `models`/`input_fields`/`id_field`/`fetch_opts`); (d) `referenced_strategies` returns the correct per-family union for a mixed inventory; (e) one test per gate (1–7) asserting the error names the resource.
- [ ] **Step 2: Implement** `idempotency.py` + the `ObjectView`/`build_wrapper_context` hooks. `_idempotency_literal` mirrors `_binding_dict_repr`/`_bindings_literal` (~lines 662–682) except `models` entries render as bare identifiers, e.g.:

```python
_idempotency: ClassVar[dict[str, Any]] = {
    "identity": ["name"],
    "scope": {"fields": ["folder", "snippet", "device"], "rule": "exactly_one"},
    "models": {"create": Addresses, "update": Addresses, "read": Addresses},
    "input_fields": ["name", "description", "tag", "ip_netmask", "ip_range",
                     "ip_wildcard", "fqdn", "folder", "snippet", "device"],
    "server_only": ["id"],
    "id_field": {"wire": "id", "attr": "id"},
    "order_sensitive": [],
    "write_only": [],
    "projections": {},
    "singleton": False,
    "update": {"verb": "replace"},
    "fetch": "list_scan",
    "mutate": "put_rmw",
    "materialize": "direct",
    "fetch_opts": {"page_limit": 200, "hydrate": True},
}
```

(Compare with the prototype's hand-written `META` in `run_prisma_access.py` lines 51–63 and `run_prisma_browser.py` lines 108–114 — the producer must reproduce both, with `models`/`materialize`/`id_field`/`fetch_opts` as the enrichments F3/F4 demanded, and the three strategy names replacing the prototype's inline branch keys.)

- [ ] **Step 3: Thread the config through the pipeline** — `render.vendor(..., idempotency=...)` → `_vendor_resources` → `build_wrapper_context(inv, operations, discovered, docs=..., idempotency=...)`; `build.py::_generate_one` passes `sub.config.idempotency` (federated) / `loaded.config.idempotency` (single-spec), exactly like `operations=` (build.py ~line 285, render.py ~line 83).
- [ ] **Step 4:** all baking tests green; `uv run nox -s gate` green; commit (`Bake per-resource idempotency metadata and strategy selection into the wrapper context`).

**Exit gate (Phase 0):** `uv run pytest tests/test_sdk_idempotency_context.py tests/test_config.py tests/test_productconfig.py tests/test_sdk_wrapper.py -v` green; `uv run nox -s gate` green; a no-idempotency build renders `ObjectView.sync == False` everywhere, `referenced_strategies` empty, and `resources.py` byte-identical (assert by rendering with and without `idempotency=None`). No live requirement yet (no runtime behavior).

---

## Phase 1 — The idempotency component: orchestrator + base + the strategy modules the two proven resources need

Translate the validated prototype into the vendored **component tree**: the `SyncMixin` orchestrator, the `base.py` Protocols + registries, and exactly the strategy modules the two proven resources reference — `fetch/list_scan`, `fetch/list_filter`, `mutate/put_rmw`, `mutate/patch_minimal`, `materialize/direct`, `materialize/get_after_write`. Wire the mixin into `resource.py.jinja`, opt in the two resources, and stand up the live quartet as the standing exit gate for every later phase. (`fetch/get` for singletons is deferred until a singleton opts in — no singleton is live-proven.)

**Effort:** L (~3–4 days). **Risk:** the engine is validated logic — the risk is translation drift; keep the per-strategy prototype mapping honest and the unit tests shape-for-shape with the prototype's checks.

### Task 1.1: `base.py.jinja` — Protocol seams + registries

**Files:** create `components/idempotency/base.py.jinja`; test in `tests/test_sdk_sync.py`.

- [ ] **Step 1:** define the three `Protocol`s (spec §5.3) and the `FETCH`/`MUTATE`/`MATERIALIZE` dicts; the only template conditional is the `NotFoundException` import split (federated: `from {{ root_package }}._runtime.exceptions import NotFoundException`; single-spec: `from ..exceptions import NotFoundException`) — re-exported for the strategies to import from `.base`.
- [ ] **Step 2: Failing test** — rendering `base.py.jinja` (both import branches) via `render._env()` `exec`s cleanly and exposes the three empty registries + the three Protocols.
- [ ] **Step 3:** implement; commit (`Add the idempotency seam protocols and strategy registries`).

### Task 1.2: `engine.py.jinja` — the orchestrator + Diff/SyncResult/exceptions

**Files:** create `components/idempotency/engine.py.jinja`; test `tests/test_sdk_sync.py`.

Contents and **prototype mapping** (translate, don't redesign — the orchestrator keeps only the UNIFORM steps; the varying branches move to strategy modules in Task 1.3):

| Generated piece | Prototype source | Notes |
|---|---|---|
| `Diff`, `SyncResult` (frozen dataclasses) | `engine.py` lines 21–35 | verbatim (spec §4.2 shapes) |
| `AbsentNotSupported`, `IdentityUnresolved` | `engine.py` lines 39–44 | verbatim |
| `_normalize(value, *, order_sensitive)` | `engine.py` `_jsonify`/`_normalize` lines 59–76 | order-INSENSITIVE lists by default, canonical `json.dumps` sort; **the projection hook (F5) lands here in Phase 5** — engine core, not a strategy |
| `SyncMixin._present`/`_writable`/`_full` | `engine.py` lines 92–101 | `_present` = `model_dump(by_alias=True, mode="json", exclude_unset=True)`; `_writable` = `to_dict()`; `_full` = `model_dump(by_alias=True, mode="json")` |
| `_extract_identity` | `engine.py` lines 104–119 | identity from `meta["identity"]` (a list — composite falls out); scope collected when set |
| `diff(desired, actual)` | `engine.py` `_comparable`/`diff` lines 141–157 | comparable set = `input_fields ∩ user-set(desired) − scope − server_only` (− `write_only`, Phase 5); changes record un-normalized wire values |
| `apply` / `absent` / `fetch` **control flow** | `engine.py` lines 122–213 | the orchestrator resolves `FETCH[meta["fetch"]]` / `MUTATE[meta["mutate"]]` / `MATERIALIZE[meta["materialize"]]` from `.base` and calls them (spec §5.2). Create builds the body via `meta["models"]["create"].model_validate(_present(desired))`, calls `self.create`, then the materialize strategy. Update calls the mutate strategy then materialize. `check_mode` never calls a mutating verb or a mutate/materialize strategy |

- [ ] **Step 1: Failing orchestrator unit tests** — `tests/test_sdk_sync.py`. Render `engine.py.jinja` + `base.py.jinja` once (single-spec branch) via `render._env()`, `exec` as a module (the `tests/test_render.py::_exec_extras_errors` pattern, ~line 37), register **canned fake strategies** into the registries, and drive `SyncMixin` through a stub resource:

```python
class StubResource(engine_mod.SyncMixin):
    _idempotency = {...}          # hand-built, per test scenario
    # canned public verbs recording calls: list/get/create/replace/update/delete
```

Cover (orchestrator-only, strategies faked so this isolates the control flow): quartet transitions incl. re-apply→unchanged; create builds the body from `models["create"]` and calls the materialize strategy; update calls the mutate strategy then materialize; `check_mode` never invokes a mutate/materialize strategy (assert the fakes were not called); normalization (enum value, nested model, list order-insensitive default + `order_sensitive` override); composite identity (2-field); `IdentityUnresolved` on unset identity; singleton `absent` raises; scope excluded from diff.
- [ ] **Step 2:** implement; commit (`Add the idempotent sync orchestrator (SyncMixin) component`).

### Task 1.3: the six strategy modules (each independently unit-tested)

**Files:** create `fetch/{list_scan,list_filter}.py.jinja`, `mutate/{put_rmw,patch_minimal}.py.jinja`, `materialize/{direct,get_after_write}.py.jinja`; `__init__.py.jinja`; extend `tests/test_sdk_sync.py`.

Each module is a small callable satisfying its Protocol and self-registering in the matching registry. **Per-strategy prototype mapping + the unit test each carries** (translate the exact branch; test the strategy in isolation with a canned wrapper):

| Strategy module | Prototype source | Behavior + isolated unit test |
|---|---|---|
| `fetch/list_scan` | `engine.py` `fetch()` list_scan branch (lines 122–138) | `self.list(all_pages=True, limit=fetch_opts["page_limit"], **scope)`; exact-match re-filter on identity wire keys; **F2**: wrap in `except NotFoundException: return None` AND empty match → `None`; `>1` → `IdentityUnresolved`; optional `hydrate` GET-by-id. Tests: 404→None, empty→None, exact match, >1→raise, hydrate GETs |
| `fetch/list_filter` | `run_prisma_browser.py` `fetch()` (lines 50–61) | `self.list(**identity, **scope)` then the same re-filter + hydrate. Tests: server-filtered candidate re-filtered exactly, hydrate GET after match |
| `mutate/put_rmw` | `engine.py` `_build_update_body` PUT branch (lines 160–166) + apply update call | body = `{**actual.to_dict(), **_present(desired)}`, pop `id_field["wire"]`, `meta["models"]["update"].model_validate(...)`, call `getattr(self, meta["update"]["verb"])(id=..., body=...)`, return the raw response. **F4**: always the metadata's model class. Tests: seeds actual + overlays user-set + drops id; calls the named verb |
| `mutate/patch_minimal` | `engine.py` PATCH branch + `run_prisma_browser.py` apply (lines 93–95) | body = only `Diff.changes` afters in `meta["models"]["update"]`; call the PATCH verb; return the raw response. Tests: only changed fields, in the patch model class, correct verb |
| `materialize/direct` | `run_prisma_access.py` (response IS the object) | return the response as-is. Test: identity pass-through |
| `materialize/get_after_write` | `run_prisma_browser.py` apply create/patch GET-after (lines 83–86, 95–97) | read `getattr(response, meta["id_field"]["attr"])`, `self.get(id=...)`, return it. **F3**. Test: id-envelope → GET materializes state |

`__init__.py.jinja` imports the vendored subset so registrations run; re-exports `SyncMixin`/`Diff`/`SyncResult`/exceptions from `.engine`.

- [ ] **Step 1: Failing per-strategy unit tests** (one cluster per module above), rendered + `exec`ed like Task 1.2, each driving the single strategy callable against a canned wrapper — mirroring the prototype's 17+13 checks split across the modules. Plus an **integration** pass: register the six real strategies and re-run the full quartet through `SyncMixin` end-to-end (F2 both absence shapes; F3 id-envelope; F4 create/update/read classes distinct; F9 verb dispatch; PUT RMW preserves unmanaged; PATCH isolates changed).
- [ ] **Step 2: Implement the six modules + `__init__`**; commit (`Add the fetch/mutate/materialize sync strategy modules`).

### Task 1.4: vendor the union in `render.vendor`

**Files:** `src/phantasos/generator/sdk/render.py` (a new `_vendor_idempotency` helper, called beside the `pagination`/`errors` writes ~line 121); tests: `tests/test_render.py`.

- [ ] **Step 1: Failing tests** — for a stub package with opted-in objects whose baked strategies span `{list_scan, list_filter}` × `{put_rmw, patch_minimal}` × `{direct, get_after_write}`, `render.vendor` writes `extras/idempotency/{__init__,base,engine}.py` + exactly the referenced strategy modules (assert the UNION: unreferenced variants like `fetch/get` are **absent**); with `idempotency=None`, **no `extras/idempotency/` directory exists** (byte-identical canary).
- [ ] **Step 2: Implement** `_vendor_idempotency(pkg_dir, referenced, ctx, env, written)`: `mkdir extras/idempotency/{fetch,mutate,materialize}` only when idempotency is present; render `base.py`/`engine.py`/`__init__.py` + each referenced strategy template; write before `resources.py` (which imports `.idempotency`). Thread `referenced_strategies(objects)` from `_vendor_resources` (it has the `ObjectView` list).
- [ ] **Step 3:** tests green; commit (`Vendor the idempotency engine and the union of referenced strategy modules`).

### Task 1.5: wire the mixin into `resource.py.jinja`

**Files:** `components/facade/resource.py.jinja`; tests: extend `tests/test_sdk_sync.py` + a byte-identical regression in `tests/test_render.py`.

- [ ] **Step 1: Failing tests** — (a) a vendored stub package with one opted-in object exposes `apply/absent/fetch/diff` and `_idempotency`; (b) rendering with `idempotency=None` produces **byte-identical** `resources.py` to today's output (golden comparison against a pre-change render).
- [ ] **Step 2: Template change** (all conditional, nothing renders for non-opted objects):

```jinja
{% if has_idempotency %}from .idempotency import SyncMixin
{% endif %}
...
{% if o.sync %}class {{ o.classname }}(SyncMixin):{% else %}class {{ o.classname }}:{% endif %}
    ...
    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {{ o.bindings_literal }}
{% if o.sync %}    _idempotency: ClassVar[dict[str, Any]] = {{ o.idempotency_literal }}
{% endif %}
```

`_vendor_resources` passes `has_idempotency=any(o.sync for o in objects)`. The model imports the literal references are already in `ObjectView.imports` (Task 0.2), so the merged import block resolves them.
- [ ] **Step 3:** tests green; commit (`Wire SyncMixin and the idempotency classvar into resource wrappers`).

### Task 1.6: minimal product opt-in + the live quartet oracles

**Files:** `products/prisma-access/sdk.yml` (objects sub), `products/prisma-browser/sdk.yml`; create the two live test templates.

- [ ] **Step 1: Opt in exactly the two proven resources** (broaden later, in Rollout):

```yaml
# products/prisma-access/sdk.yml — under `- slug: objects`
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

```yaml
# products/prisma-browser/sdk.yml — top level
idempotency:
  defaults:
    read_only:
      - id
  resources:
    application_group:
      computed:
        - applications
```

(`address: {}` bakes `fetch=list_scan`, `mutate=put_rmw`, `materialize=direct`; `application_group` bakes `mutate=patch_minimal`, `materialize=get_after_write`, and `fetch=list_scan` with `hydrate=True` — the browser prototype lists-and-matches then GETs; if the tenant proves the `application_group?name=` filter functional per F1, override `fetch: list_filter` and re-verify. `applications` is excluded from diff exactly as the prototype's `server_only` did — `run_prisma_browser.py` line 112; Phase 5's projection brings it under management.) NOTE: the prisma-access opt-in trips the Phase-0 F8 pagination gate until Phase 2 lands — add Task 2.1's one-line `pagination:` block now and prove it in Phase 2.
- [ ] **Step 2: Live quartet templates**, modeled on `products/prisma-access/overrides/tests/test_scm_crud_live.py.jinja` (same `_REQUIRED_ENV` skip-guard, unique `phx-sync-<uuid>` names, `finally` cleanup):
  - `test_scm_sync_live.py.jinja` — mirrors `run_prisma_access.py` main() steps 1–7 through the BUILT SDK: `client.objects.address.apply(...)` create → re-apply identical unchanged → modify (`ip_netmask` changed, `description` omitted) → assert diff isolates `ip_netmask` AND the refetched `description` survived (put_rmw proof) → check_mode predicts without writing → `absent` → re-`absent` unchanged → `fetch` → None.
  - `test_sdk_sync_live.py.jinja` — mirrors `run_prisma_browser.py`: create via id-envelope + get_after_write materializes `after` → re-apply unchanged (model-split proof) → description drift → patch_minimal (diff isolates `description`) → check_mode → absent quartet tail.
  - Both files match the `nox -s live` glob (`tests/test_*_live.py`, noxfile ~line 301), so they run automatically.
- [ ] **Step 3: Rebuild + run:** `uv run nox -s smoke`, then `uv run nox -s live`.

**Exit gate (Phase 1):** offline — `uv run pytest tests/test_sdk_sync.py tests/test_sdk_idempotency_context.py tests/test_render.py -v` + `uv run nox -s gate` green, adem/byte-identical regression green (no `extras/idempotency/` for non-opted products). **Live — the full idempotency quartet green on BOTH products** (this is the prototype's 17/17 + 13/13 rehomed onto generated component code; show the output). Commit (`Opt in address and application_group with live sync quartets`).

---

## Phase 2 — Pagination under `list_scan` (F8)

`fetch/list_scan` is only correct with full pagination. The wrapper `_list` already paginates when a `pagination:` component exists (`resource.py.jinja` lines 63–75); prisma-access never configured one, so `all_pages=True` silently returned page 1. **Decision: fix at the wrapper layer by enabling the existing offset component for prisma-access — the strategy stays a plain `self.list(all_pages=True, ...)` caller.** No strategy-side paging: it would duplicate the pagination component and bypass the wrapper seam every other behavior (retry, enum coercion, multi-binding) rides.

**Effort:** S–M (~1 day). **Risk:** SCM offset semantics must match the template's defaults; verified live.

### Task 2.1: enable + verify offset pagination for prisma-access

**Files:** `products/prisma-access/sdk.yml`; tests: extend the live sync template + one offline stub test.

- [ ] **Step 1:** add (top level — the vendor writes `pagination.py` per sub from the product component, `render.py` ~line 121):

```yaml
pagination:
  type: offset
```

SCM list envelopes are `{data, limit, offset, total}` — exactly the `OffsetPagination` defaults (`config.py` ~lines 79–92), so no field overrides.
- [ ] **Step 2: Offline test** (extend `tests/test_sdk_sync.py`): a stub list verb returning 2 pages through the rendered offset `paginate` proves `fetch/list_scan` finds an object on page 2 (the exact false-absent → duplicate-create failure NOTES F8 predicts).
- [ ] **Step 3: Live proof** (extend `test_scm_sync_live.py.jinja`): create 3 uniquely-prefixed addresses, assert `client.objects.address.list(folder="Shared", limit=2, all_pages=True)` returns all of them (pagination walks past page 1), and that `fetch` finds the 3rd; cleanup in `finally`.
- [ ] **Step 4: Cursor sanity for prisma-browser** — already configured (`pagination: {type: cursor}`); assert in `test_sdk_sync_live.py.jinja` that `list(all_pages=True)` succeeds (small collections; the assertion is "no error + superset of page 1").
- [ ] **Step 5:** the Phase-0 F8 gate now passes for prisma-access; `uv run nox -s smoke && uv run nox -s live`.

**Exit gate (Phase 2):** offline gate green; live — pagination proof + the quartet still green on both products. Commit (`Enable offset pagination for prisma-access; list_scan pages fully`).

---

## Phase 3 — The injectable-token seam: `from_access_token` (validated §9)

Additive, independent of idempotency (it rides the auth component, so **all** auth-bearing products get it — the one deliberate exception to byte-identical, called out in the CHANGELOG).

**Effort:** S (~0.5–1 day).

### Task 3.1: auth template + facade/composer constructors

**Files:** `components/auth/scm_oauth.py.jinja`, `components/facade/client.py.jinja`, `components/facade/composer.py.jinja`; tests: `tests/test_render.py` (following `test_federated_auth_emits_bearer_client_and_config_factory` ~line 156), plus a live token-seam test.

- [ ] **Step 1: Failing render tests** — single-spec render contains `class _ProviderTokenSource` + `def api_client_from_token`; federated render contains `def configuration_from_token`; `client.py.jinja`/`composer.py.jinja` renders contain `def from_access_token`; `__all__` updated.
- [ ] **Step 2: Implement** (prototype mapping: `engine.py::ProviderTokenSource` lines 48–55, live-proven consulted-per-request in `run_prisma_access.py` lines 68–85, 153–162):

```python
class _ProviderTokenSource:
    """Duck-types TokenManager's `.token()` for a caller-owned token."""
    def __init__(self, token):
        self._provider = (lambda: token) if isinstance(token, str) else token
    def token(self) -> str:
        return self._provider()


def api_client_from_token(token, *, host: str = DEFAULT_BASE_URL) -> ApiClient:
    cfg = {{ config_class_name }}(token_manager=_ProviderTokenSource(token), host=host)
{% if has_retry %}    cfg.retries = default_retry()
{% endif %}{% if federated %}    return _BearerApiClient(cfg){% else %}    return ApiClient(cfg){% endif %}
```

plus, in the `{% if federated %}` block, `configuration_from_token(token, *, host=...)` mirroring `configuration_from_credentials` (~line 141). Facade `client.py.jinja` (inside `{% if has_auth %}`, beside `from_env` ~line 52) and `composer.py.jinja` (beside `from_env` ~line 72) each gain a `from_access_token` classmethod (single-spec wraps `api_client_from_token`; the composer wraps `configuration_from_token`).
- [ ] **Step 3: Live token-seam test** (append to both live sync templates): build the client via `Client.from_access_token(counting_provider)` where the provider wraps a real `TokenManager` and counts calls; run two reads; assert count ≥ 2 (per-request pull) and the str-token path performs one authenticated list — the prototype's `n=14` observation, minimized.
- [ ] **Step 4:** `uv run nox -s smoke && uv run nox -s live`; commit (`Add from_access_token client construction (str or callable provider)`).

**Exit gate (Phase 3):** render tests + offline gate green; live seam checks green on both products.

---

## Phase 4 — Symmetric scope validator patch pass (F7 — UX only, lowest priority)

The server already rejects 0-/2-container bodies (validated live, `run_prisma_access.py` scope block); this pass exists purely for earlier, clearer errors. **It is deferrable without risk — if schedule pressure hits, ship Phases 0–3+5–7 and file this as a follow-up.**

**Effort:** S (~1 day).

### Task 4.1: `patch_scope_validators`

**Files:** `src/phantasos/generator/sdk/patches.py` (new pass after `patch_oneof_missing_imports`); call site in `build.py::_generate_one` **after** `apply_generic_patches`, gated on the sub's idempotency config having a scope (config-dependent, so it does NOT join `apply_generic_patches`' unconditional dict, ~line 259); tests: `tests/test_sdk_build.py`-style unit on a fixture model file + a real-artifact assertion.

- [ ] **Step 1: Failing tests** — the pass injects a `model_validator(mode="after")` into exactly the **mutating input model files** it is given (the create/update body models from the wrapper context's `_idempotency["models"]` — NOT every model); the validator raises on 0 and 2 set scope fields; **server-echo guard:** instances with `id` set validate clean; idempotent (second run = 0 changes); anchor-absent files skipped unchanged (house pattern, cf. `patch_oneof_unwrap_serializer` ~line 160).
- [ ] **Step 2: Implement** — injected method (template string, `_ensure_model_validator_import` sibling of `_ensure_model_serializer_import` ~line 149):

```python
    @model_validator(mode="after")
    def _phantasos_scope_exactly_one(self):
        """phantasos: exactly one of the scope containers must be set on a
        user-authored mutation body. Skipped for server echoes (id set)."""
        if getattr(self, "id", None) is not None:
            return self
        set_ = [f for f in ("folder", "snippet", "device") if getattr(self, f, None) is not None]
        if len(set_) != 1:
            raise ValueError(f"exactly one of folder/snippet/device must be set (got {set_ or 'none'})")
        return self
```

(field tuple interpolated from the scope spec; the model list comes from the same producer facts as `_idempotency["models"]`.)
- [ ] **Step 3: Real-artifact check** (extend the built prisma-access ring): `Addresses(name=..., folder=..., snippet=..., ip_netmask=...)` raises at construction; a dict with `id` + no container round-trips `model_validate` — settles spec §13's open echo-guard question against real payloads; if an echo without `id` and without a container surfaces, drop the validator to create-only models and record the decision.
- [ ] **Step 4:** `uv run nox -s smoke && uv run nox -s live` (the quartet must stay green — the validator must not reject the `mutate/put_rmw` bodies). Commit (`Add client-side scope mutual-exclusion validator for scoped products`).

**Exit gate (Phase 4):** offline + real-artifact assertions green; live quartet unaffected.

---

## Phase 5 — Per-field projections (F5) + write-only fields (F6 escape hatch)

Makes the remaining awkward shapes manageable instead of `sync: false`-only. Both land in the **engine core** (`_normalize`/`diff` in `engine.py.jinja`) — NOT a new strategy family (one projection type so far → YAGNI; promote to a `compare` family only when a second appears).

**Effort:** M (~1–2 days).

### Task 5.1: `projections:` (F5)

**Files:** `engine.py.jinja` (`_normalize`/`diff`), `idempotency.py` (already passes the annotation through, Task 0.2), tests: `tests/test_sdk_sync.py` + live.

- [ ] **Step 1: Failing unit test** — metadata `{"projections": {"applications": "id"}}`; actual carries `applications=[{"id": "a1", "name": "..."}]`, desired carries `["a1"]` → **no drift**; desired `["a2"]` → drift with un-normalized wire values in `Diff.changes`.
- [ ] **Step 2: Implement** — in `diff`, before normalization, project the **actual** side of an annotated field: each dict item → `item[subfield]` (non-dict items pass through). Prototype mapping: the annotation NOTES F5 proposed for the exact `application_group.applications` `list[str]`-vs-`list[obj]` mismatch the prototype excluded via `server_only` (`run_prisma_browser.py` line 111 comment).
- [ ] **Step 3: Opt the field in live** — flip prisma-browser's `application_group` from `computed: [applications]` to `projections: {applications: id}` and extend the live quartet: manage `applications`, prove no false drift on re-apply and real drift on membership change. (Requires a stable application id; reuse the composite-identity read of `run_prisma_browser.py` lines 166–180 to pick one, or skip that leg when the tenant has none.)

### Task 5.2: `write_only:` (F6)

**Files:** `engine.py.jinja` (comparable set), `idempotency.py` (gate resolution), tests.

- [ ] **Step 1: Failing tests** — baking: a resource whose managed field is missing from the read model passes the F6 gate **iff** listed under `write_only:` (else the Phase-0 error). Engine: a `write_only` field is excluded from `diff`, still sent on create, and included in the `put_rmw` overlay when user-set (documented partial sync — drift on it is undetectable by design).
- [ ] **Step 2: Implement** both sides; extend the F6 gate message to offer `write_only:` as the second resolution.
- [ ] **Step 3 (optional live):** opt in prisma-browser `user_group` with `write_only: [userIds]` (the exact F6 case from NOTES) and run its quartet — description-drift only.

**Exit gate (Phase 5):** unit + baking tests green; live quartet green including the `applications`-managed leg; offline gate green. Commit (`Support per-field projections and write-only managed fields`).

---

## Phase 6 — Test consolidation + broader rollout

The per-phase tests already exist; this phase closes coverage gaps, proves the negative space, and widens the opt-in.

**Effort:** M (~2 days).

- [ ] **Task 6.1: Negative-space regression suite.** (a) adem builds with zero idempotency artifacts (**no `extras/idempotency/` directory**, no `SyncMixin` import, no `_idempotency`); (b) per spec §6 semantics "block present → every CRUD-complete object is a candidate": assert the gate-vs-default behavior precisely (candidates with inferable identity sync by default; `sync: false` opts out; uninferable + unlisted fails the build). Encode these outcomes as baking tests if Phase 0 didn't already.
- [ ] **Task 6.2: Real-artifact ring** (pattern: `tests/test_cli_cache_real.py` / `real_sdk` fixtures): the BUILT prisma-browser SDK's `application_group` exposes `apply/absent/fetch/diff` with the §4.1 signatures and `_idempotency["mutate"] == "patch_minimal"` / `["materialize"] == "get_after_write"`; the built prisma-access `address._idempotency` carries `fetch == "list_scan"`, `mutate == "put_rmw"`, `materialize == "direct"`, `update == {"verb": "replace"}`, scope trio; both built packages contain an `extras/idempotency/` tree holding **only** the referenced strategy modules; `Client.from_access_token` exists on both. Skips when the sibling SDKs aren't built.
- [ ] **Task 6.3: Broaden the prisma-access opt-in** (still conservative): `tag: {}`, `address_group: {order_sensitive: [static]}` under objects — each must pass the Phase-0 gates at build; extend the live quartet to `tag` (cheap, pure-reshape object). Resources that trip a gate get an explicit `sync: false` with a YAML comment naming the reason (e.g. `auto_tag_action` — no natural key). Full-catalog rollout (~130+ resources) is a separate follow-up, not this plan.
- [ ] **Task 6.4: Full ladder:** `uv run nox -s gate` → `uv run nox -s smoke` → `uv run nox -s live` (all quartets + pagination + token seam), plus `uv run nox -s sdk-docs` (built SDKs must still doc-build with the new extras package).

**Exit gate (Phase 6):** the entire ladder green; every suite named in this plan passing in one run. Commit (`Broaden idempotency opt-in and close test coverage`).

---

## Phase 7 — Docs & context

**Effort:** S (~0.5–1 day). No doc file is committed by the implementer — write them and hand off.

- [ ] **Task 7.1:** `CHANGELOG.md` `## [Unreleased]` → `### Added`: idempotent sync (`apply`/`absent`/`fetch`/`diff`, opt-in via `sdk.yml idempotency:`, composable fetch/mutate/materialize strategies per ADR-0004), `from_access_token` (note: emitted for all auth-bearing products), prisma-access offset pagination, scope validator.
- [ ] **Task 7.2:** `.agents/context/sdk-generator.md` — narrative for the idempotency component tree (orchestrator + base + strategy families), the metadata producer + strategy auto-selection + union-vendoring + gates, the pagination dependency; `.agents/context/product-config.md` — the `idempotency:` block reference (block-style examples, incl. the strategy-override escape hatch). Then `uv run nox -s context` and confirm `-- --check` passes.
- [ ] **Task 7.3:** Generated-SDK MkDocs: a "Sync operations" guide page (wrapper-surface style, like the CRUD guide) via `generator/sdk/docs.py` — apply/absent semantics, check_mode, `SyncResult`/`Diff`, partial-sync caveats for `write_only`, and a note that strategies are auto-selected (custom strategies documented as the extensibility path). Keep the `sdk-docs` nox assertions green. (If the docs-stage plumbing balloons, split to a follow-up; the spec deferred this to plan discretion.)
- [ ] **Task 7.4:** Tell the human which doc files are ready to review and commit.

**Exit gate (Phase 7):** `uv run nox -s context -- --check` and `uv run nox -s sdk-docs` green; final full ladder green; PR → `develop` (squash) with the code; docs left for human commit.

---

## Prerequisites & risks (weigh before starting)

1. **Pagination correctness is load-bearing (F8).** An incomplete `list_scan` turns "exists" into "absent" and `apply` into a duplicate-create `OBJECT_ALREADY_EXISTS`. Hence the Phase-0 build gate (can't opt in a `list_scan` resource without a pagination component) and the Phase-2 live page-walk proof. SCM offset semantics matched the template defaults in manual checks; if the live proof disagrees, fix the component config, never the strategy.
2. **`fetch` is O(collection) everywhere (F1).** On large tenants every `apply` lists the whole (scoped) collection. Bounded today (scope-trio narrows prisma-access scans; prisma-browser collections are small), but a large unfiltered collection opting in is a real cost cliff. The baked `fetch` strategy + `fetch_opts.page_limit` are inspectable/tunable; revisit (server-side filters, caching, a new fetch strategy) only when a real consumer hits it.
3. **Resources that cannot be synced.** No natural key, write-only managed fields, or no update verb → the build fails until a human decides (`identity:`, `write_only:`, or `sync: false`). Deliberate friction; expect the Phase-6 rollout to surface a handful per sub-package.
4. **Server-echo guard for the scope validator** (spec §13): "skip when `id` is set" is checked against real payloads in Phase 4 Step 3; the documented fallback (create-only validator + engine-side rule) is pre-agreed, so a surprise costs hours, not a redesign.
5. **Composite identity is construction-validated, not quartet-proven** (NOTES): `application` (type+name) exercised the read path only. Don't opt `application` into sync until its quartet is run; the orchestrator mechanism (identity-as-list) is covered by unit tests either way.
6. **GET-after-write doubles mutation-path calls** on `materialize/get_after_write` products (prisma-browser). Accepted: correctness (materialized `after`) over one extra request; retry/backoff already applies.
7. **`from_access_token` changes all auth-bearing products' bytes** — the one intentional exception to "byte-identical unless opted in". Called out in the CHANGELOG; the constructor is inert unless called.
8. **More moving parts than a monolith (ADR-0004 consequence).** An engine core + `base.py` + N strategy modules + per-resource selection is more files than one `sync.py`. Mitigations: each strategy is independently unit-tested (Task 1.3); the union-vendoring keeps a product's `extras/idempotency/` to only what it uses; the callers' interface is still four methods. The offset is real but chosen deliberately — it is what keeps the engine open/closed and avoids the pan-scm per-module duplication.
9. **Metadata literal size:** ~16 keys × opted-in resources in `resources.py`. At full prisma-access rollout that is a few thousand lines of literals — same order as `_bindings` today; acceptable, and it keeps behavior + strategy selection unforgeable-by-drift (the engine executes *from* the literal).

## Self-Review

**Findings coverage (now per strategy):** F1 → Phase 0 fetch selection + `fetch/list_scan` default (Task 1.3); F2 → `fetch/list_scan` 404/empty→None (Task 1.3); F3 → Phase 0 `materialize`/`id_field` + `materialize/get_after_write` (Task 1.3); F4 → Phase 0 `models` + the mutate strategies' model-class use (Task 1.3); F5 → Task 5.1 (engine-core hook); F6 → Phase 0 gate + Task 5.2; F7 → Phase 4 (framed UX, deferrable); F8 → Phase 0 gate + Phase 2; F9 → Phase 0 `mutate`/`update.verb` + the mutate strategies' verb dispatch. Confirmed-good behaviors are each pinned by a named unit test (orchestrator or strategy) and a live quartet leg.

**Spec-alignment log:** the engine is the ADR-0004 orchestrator + strategy components, not a monolith (`extras/idempotency/` package, not `extras/sync.py`); `fetch` default is `list_scan` (F1); `_idempotency` carries the three strategy names + `models`/`materialize`/`id_field`/`fetch_opts`/`write_only`/`projections` (F3/F4/F5/F6); `server_only` derives from annotations + the id field rather than re-reading spec `readOnly` (documented simplification, Task 0.2); the scope validator is deferrable UX (F7); `absent` keeps the model-or-identity-object contract (kwargs sugar not built).

**Sequencing rationale:** metadata + strategy selection (0) → orchestrator + base + the needed strategy modules (1) → pagination (2) are the load-bearing chain and land first; the auth seam (3) is independent and small; the validator (4) is deferrable; the engine-core annotations (5) unlock the awkward resources before rollout breadth (6); docs last (7). Phases 1+2 share the prisma-access opt-in, so their `sdk.yml` edits land together (noted in Task 1.6).

**Placeholder scan:** every task names its files/functions with line anchors, its prototype source lines where applicable, its failing-test-first step, and a runnable exit command. No "TBD".
