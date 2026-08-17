# SDK idempotent sync (for the Ansible target) — design spec

- **Date:** 2026-07-12
- **Status:** Design spec (grilled; all decisions locked) — **validated end-to-end against a real SCM tenant on 2026-07-12** via a throwaway prototype (`prototypes/sync-engine/`, see `NOTES.md`). Core design confirmed; several concrete assumptions were corrected — see **§0 Validation findings**. No production code yet. Precedes the implementation plan.
- **Parent:** `docs/plans/2026-07-12-ansible-collection-generator-feasibility.md` (this spec renders its Section 3 SDK extensions / components 1–2).
- **ADRs:** ADR-0002 (idempotent sync is an SDK operation), ADR-0003 (idempotency metadata lives in `sdk.yml`), **ADR-0004 (idempotency strategies are composable per-resource components — supersedes the monolithic `SyncMixin` shape; §5 renders it)**. Referenced, not restated.
- **Branch:** prototyping on `sdk-ansible` (off `develop`). The eventual implementation lands via a `feature/<slug>` PR into `develop` (squash, `## [Unreleased]`) per the branching workflow.
- **Scope:** the **SDK generator** (`src/phantasos/generator/sdk/`) plus the product-config layer (`src/phantasos/config.py`, `productconfig.py`). Three additive changes: (1) a high-level sync operation on the resource wrapper, (2) a new data-driven idempotency component that implements it, (3) an injectable-token auth seam. Plus the consumer-facing interface contract the later Ansible plan builds against.

---

## 1. Goal

Give every generated SDK an **idempotent sync capability** as a first-class, tested resource operation:

```python
client.address.apply(desired)            # fetch → diff → create/update/no-op
client.address.absent(desired)           # fetch → delete/no-op
client.address.fetch(name="corp-dns", folder="Shared")   # Model | None
client.address.diff(desired, actual)     # typed Diff
```

so that a later effort can generate an Ansible collection whose modules are pure declarative shells, and so the generated CLI can later grow `apply`/`--if-changed` from the same engine. Per ADR-0002 the fetch→diff→mutate flow is defined **once in the SDK**, next to the models it reasons about — not re-orchestrated per consumer.

The reference community project for the same API family — **cdot65/pan-scm-ansible + pan-scm-sdk** — validates the direction (collection depends on the published SDK; server-side `fetch(name, scope)` existence check; PUT-replace with `id` popped to the URL; a pre-supplied `access_token` path) and exhibits the exact failure mode this design eliminates: its drift logic lives **per-module** in the Ansible layer as a hand-maintained `needs_update` field whitelist that silently ignores unlisted fields, so drift on unlisted fields is missed and the logic diverges per resource. Pushing diff/sync into the generated SDK removes that whole bug class for both CLI and Ansible.

## 0. Validation findings (2026-07-12, live tenant)

A throwaway prototype (`prototypes/sync-engine/`) ran the full idempotency quartet +
edge cases against the real tenant for BOTH products: **prisma-access address 17/17
checks, prisma-browser application_group 13/13 checks**. What held, and what must
change:

**Confirmed live (design is sound):** high-level `apply`/`absent` idempotency
(create→re-apply-unchanged→modify→delete), `fetch → Model | None`, typed
`Diff`/`SyncResult`, desired-subset diff off the input schema, **PUT
read-modify-write preserving unmanaged fields**, **PATCH-minimal**, `check_mode`
prediction with no write, the **`from_access_token` seam** (callable provider
consulted per-request, wired to `access_token`), **alias-aware diff** (camelCase
`by_alias`), and scope excluded-from-diff / carried-from-actual.

**Corrections folded into this spec (detail in `prototypes/sync-engine/NOTES.md`):**

- **F1 — the SCM `name=` list filter is NON-FUNCTIONAL** (returns empty even for
  existing committed objects). `fetch` MUST default to **`list_scan`** (list-and-
  match client-side); `list_filter` is opt-in only where proven per-resource
  (prisma-browser `application_group` works; prisma-access `address` does not).
  Amends §3 and §5.2/§5.3 — the "universal `name=` filter" assumption is false.
- **F2 — "absent" surfaces as a 404 OR as an empty list.** `fetch` must treat both
  not-found exceptions and empty match-sets as `None`. Amends §5.3.
- **F3 — mutation responses are often id-only envelopes** (prisma-browser
  `CreatedIdResponse`; prisma-access returns the full object). The engine must
  **GET-by-id after create/update** when the response is an envelope; the
  `_idempotency` metadata must encode response shape + id path. Amends §5.3.
- **F4 — severe model heterogeneity** (prisma-browser: create/patch/put/get are
  DIFFERENT classes). Metadata needs the create-input model, the patch/put-input
  model(s), AND the read model — not one `input_fields` list. Amends §5.2.
- **F5 — request/response shape mismatch on the same field** (a create field can be
  `list[str]` while the GET echoes `list[obj]`) → false drift without a per-field
  projection/annotation. New annotation requirement; amends §6/§7.
- **F6 — write-only managed fields** (a managed field absent from the read model →
  drift undetectable) → `sync: false` or documented partial-sync + a build-time
  gate. Amends §8.
- **F7 — the scope validator is defense-in-depth, NOT a correctness gap.** The
  server already rejects 0-/2-container bodies (400). §10's "malformed update slips
  to the server" justification is false — the validator is fail-fast UX only.
- **F8 — the built SDK's `_list` ignores `all_pages`** (first page only). Because
  F1 forces `list_scan`, **real cursor/offset pagination is now load-bearing** for
  `fetch` correctness on large collections. New risk; amends §13.
- **F9 — update verb name varies** (`replace` for PUT, `update` for PATCH); the
  engine takes the verb + strategy from metadata. Amends §5.3.

**Net:** prisma-access is no longer "more favorable" for `fetch` — F1 forces
O(collection) scans everywhere, making pagination correctness (F8) and fetch cost
the real scaling risks. Everything else in the design survived contact with the
tenant.

## 2. Non-goals

- **Everything Ansible-layer.** Modules, `module_utils`, the httpapi connection plugin, `products/<name>/ansible.yml`, doc-fragments, the integration-quartet generator, `phantasos ansible build` — all downstream of this spec. Where Ansible is relevant here, only the SDK-side **contract** it consumes is specified (§4).
- **CLI `apply` / `--if-changed`.** A noted future consumer of the same engine; not built in this effort.
- **Behavior change for products that don't opt in.** A product without an `idempotency:` block in `sdk.yml` generates **byte-identically to today** — no new module, no new methods, no new validators.
- **Bulk/batch sync**, client-side name filtering beyond what `fetch` needs, and any change to the existing CRUD wrapper surface.

## 3. Background — what exists, what's missing

The generated SDK already has the two structural idioms this design extends:

- **Data-driven wrappers.** Each `<Object>Resource` in `extras/resources.py` (template: `src/phantasos/generator/sdk/components/facade/resource.py.jinja`) carries a `_bindings: ClassVar[dict[str, list[dict]]]` baked by `build_wrapper_context` (`generator/sdk/wrapper.py`); generic helpers `_select`/`_to_raw`/`_call`/`_fetch`/`_list`/`_serialize` interpret it at runtime. One code path, per-resource data. The idempotency engine mirrors this exactly with a per-resource `_idempotency` classvar (§5).
- **Pull-model auth.** `extras/auth.py` (template: `components/auth/scm_oauth.py.jinja`) defines `TokenManager` and a `Configuration` subclass whose `access_token` **property** calls `self._token_manager.token()` — read fresh on every request. The `from_access_token` seam (§9) plugs a caller-owned token source into that same property, so external refresh is transparent.

What's missing is everything above raw CRUD: there is no "does this object already exist by its natural key", no field-aware comparison, and no single operation that converges server state to a desired state. The per-resource facts that comparison needs (natural identity, server-computed fields, the SCM container trio) are partly in the IR (`OperationInfo.body_fields` = the input schema; `SubVerb` `patch`/`put`; `ParamInfo.location`) and partly human knowledge — which per ADR-0003 is declared in `sdk.yml` and **baked into the SDK at build time**, never supplied at call time.

Per-product scan facts that shaped the design (from the feasibility report, §4):

- **prisma-access** (~156 resources / 808 ops, 12 subpackages): PUT-replace only (zero PATCH), `readOnly` consistently on `id`, uniform SCM shape with the `folder`/`snippet`/`device` scope trio. **⚠ Correction (F1): the `GET /<collection>?name=` filter is NON-FUNCTIONAL on the live tenant** — `fetch` must `list_scan`, so this target is *not* more favorable for lookup despite its regularity.
- **prisma-browser** (14 resources / 95 ops): mixed PATCH + PUT, `id` **never** marked `readOnly` (so the diff must key off the **input** schemas, which the spec cleanly separates, e.g. `BaseApplicationInput`), some resources lack a name list-filter (fetch falls back to list-all-and-match), one composite identity (Application: `type` + `name`).

## 4. The consumer-facing contract (what the Ansible plan builds against)

This section is the frozen public API. Everything after it is how the generator delivers it.

### 4.1 Methods on the resource wrapper

For every opted-in resource, `client.<resource>` (federated: `client.<sub>.<resource>`) gains four methods:

```python
def apply(self, desired: Model, *, check_mode: bool = False) -> SyncResult: ...
def absent(self, desired_or_identity: Model, *, check_mode: bool = False) -> SyncResult: ...
def fetch(self, **identity_and_scope: Any) -> Model | None: ...
def diff(self, desired: Model, actual: Model) -> Diff: ...
```

- `apply` ensures the resource exists and matches `desired`; `absent` ensures it is gone. Both extract **identity + scope from the `desired` object itself** (raising `IdentityUnresolved` if the identity fields are unset); the standalone primitives take **explicit kwargs** (`fetch(name="corp-dns", folder="Shared")`).
- `fetch` returns the typed model or **`None` when absent** — the raw-API 404 (and the empty-filtered-list case) is absorbed internally. **No exception-as-control-flow** for existence.
- `diff` is pure (no I/O): compare a desired against a fetched actual under the semantics of §7.

### 4.2 Return shapes

Frozen dataclasses, vendored once in the new `extras/idempotency/engine.py` module (§5):

```python
@dataclass(frozen=True)
class Diff:
    changed: bool
    # wire-key -> {"before": <json value>, "after": <json value>};
    # empty dict (and changed=False) when in sync.
    changes: dict[str, dict[str, Any]]

@dataclass(frozen=True)
class SyncResult:
    changed: bool
    action: Literal["created", "updated", "deleted", "unchanged"]
    before: dict[str, Any] | None      # wire-key dict of the pre-state (None on create)
    after: dict[str, Any] | None       # wire-key dict of the post-state (None on delete)
    diff: Diff
    # typed views of the same states, when a model is available
    before_model: Any | None = None
    after_model: Any | None = None
```

`before`/`after` are **JSON-serializable wire-key dicts** (`model_dump(mode="json", by_alias=True)`) — directly usable as Ansible `diff`/return payloads — with the typed models alongside for SDK/CLI callers. `Diff.changes` keys are wire keys for the same reason.

### 4.3 Errors

Real API failures propagate as the SDK's **existing typed exceptions unchanged** — `UnauthorizedException` (auth failed even after the caller's refresh), `BadRequestException` (4xx validation), `ApiException` for 409, `ServiceException` for 5xx — all already re-exported by the errors component (`components/errors/{list_error,nested_error}.py.jinja` re-export from `..exceptions`). The sync layer adds exactly **two** new exceptions, defined in `extras/idempotency/engine.py`:

```python
class AbsentNotSupported(Exception):
    """absent() called on a singleton resource (no delete/create lifecycle)."""

class IdentityUnresolved(Exception):
    """The identity could not be resolved: identity fields unset on `desired`,
    or the fetch lookup matched more than one object."""
```

One error contract for both CLI and Ansible: `SyncResult` for outcomes, `Model | None` for existence, typed exceptions for failures.

### 4.4 Client construction

```python
client = Client.from_access_token(token, *, host: str = DEFAULT_BASE_URL)
# token: str | Callable[[], str]
```

Additive alongside `from_env`/`from_credentials`. A bare string is normalized to a constant provider; a callable is invoked per request through the existing `access_token` property, so a caller that owns token refresh (the future httpapi plugin, which 401-retries and re-fetches) is transparent to the SDK. Needs only host + token source — no scope/secret, no `TokenManager` grant. See §9.

## 5. Change 1+2 — the idempotency engine as composable strategy components

> **Superseded (ADR-0004):** earlier drafts of this section described a single
> monolithic `SyncMixin` with inline `if meta[...]` branches for
> fetch/update/response handling. That shape is **superseded by ADR-0004**: the
> engine is a thin orchestrator plus three families of small, swappable **strategy
> components** — mirroring how `pagination` is already a per-product component. The
> public interface is unchanged (`apply`/`absent`/`fetch`/`diff`); only the
> internals are now vendored as named, per-resource-selected modules. This section
> renders that decomposition.

### 5.1 Shape — a thin orchestrator + three strategy families

A new component directory `src/phantasos/generator/sdk/components/idempotency/` —
peer to `facade/`, `auth/`, `pagination/`, `errors/`, `retry/`. Unlike those (one
template each), it vendors a small **tree** of modules under
`<pkg>/extras/idempotency/`, and only when the product opts in:

```
extras/idempotency/
  __init__.py          # re-exports Diff / SyncResult / the two exceptions + the engine
  base.py              # the Protocol seam contracts + the three registries
  engine.py            # the orchestrator (SyncMixin) + Diff/SyncResult + exceptions
  fetch/               # list_scan.py | list_filter.py | get.py   (union-vendored)
  mutate/              # put_rmw.py | patch_minimal.py            (union-vendored)
  materialize/         # direct.py | get_after_write.py           (union-vendored)
```

Only the **union** of strategy modules the opted-in resources actually reference is
vendored (§5.5) — finer-grained than `pagination` (one-per-product), because
fetch/mutate/materialize legitimately differ resource-to-resource within one
product (validated: prisma-access needs list_scan + put_rmw + direct;
prisma-browser needs list_filter + patch_minimal + get_after_write).

The three families, each a set of **named variants** — one plain callable per
variant, receiving the resource wrapper `self` so it can reach
`self.list/get/create/replace/update/delete`:

- **fetch** — find the existing object by identity (+scope) → `Model | None`:
  - `list_scan` (default per F1) — `self.list(all_pages=True, limit=page_limit,
    **scope)`; exact-match re-filter on identity wire keys client-side; absorbs
    both `NotFoundException` and an empty match set → `None` (F2); `>1` match →
    `IdentityUnresolved`; optional `hydrate` GET-by-id after the match.
  - `list_filter` — `self.list(**identity, **scope)` (server-side name filter),
    then the same exact-match re-filter (+ optional hydrate). Opt-in only where the
    filter is proven functional for that resource.
  - `get` (singleton) — `self.get()` with no identity args; `NotFoundException` →
    `None`.
- **mutate** — turn a `Diff` into a wire mutation, return the **raw response**:
  - `put_rmw` — seed `actual.to_dict()`, overlay the user-set desired
    (`by_alias`, `exclude_unset`), drop `id`, validate into
    `meta["models"]["update"]`, call the PUT verb from metadata (F9, e.g.
    `replace`).
  - `patch_minimal` — only `Diff.changes` afters, validate into the patch model,
    call the PATCH verb (e.g. `update`).
- **materialize** — produce the post-state `after` from a mutation response:
  - `direct` — the response IS the object (prisma-access).
  - `get_after_write` — the response is an id-only envelope (F3); read the id off it
    and `self.get(id=...)` to materialize state.

### 5.2 The orchestrator (`SyncMixin`) — the uniform steps

The orchestrator owns every step that does NOT vary, and delegates only the three
that do. Its interface is unchanged; it mixes into an opted-in wrapper exactly as
`_bindings` does (§5.8):

```python
class SyncMixin:
    """Thin idempotent-sync orchestrator. Owns the uniform control flow;
    delegates fetch/mutate/materialize to the strategy named in `_idempotency`."""
    _idempotency: ClassVar[dict[str, Any]]

    def apply(self, desired, *, check_mode: bool = False) -> SyncResult: ...
    def absent(self, desired_or_identity, *, check_mode: bool = False) -> SyncResult: ...
    def fetch(self, **identity_and_scope) -> Any | None: ...
    def diff(self, desired, actual) -> Diff: ...
```

**Orchestrator-owned (engine core — never a strategy):**

- **identity + scope extraction** from the `meta["identity"]` list (composite
  identity falls out for free) and `meta["scope"]`.
- the **desired-subset diff** (§7): comparable set =
  `input_fields ∩ user-set(desired) − scope − server_only`; wire-form
  normalization; lists order-insensitive by default; the per-field **projection
  hook** (F5) lives here (NOT a `compare` component family — YAGNI until a second
  projection type exists).
- **create-body construction** from `meta["models"]["create"]` (create is an
  orchestrator path; only the *update* mutation is a `mutate` strategy).
- `check_mode` prediction with no write, and **SyncResult assembly**.

Control flow (delegated steps in **bold** call the strategy registry):

```
apply(desired, check_mode):
    identity, scope = _extract_identity(desired, meta)          # IdentityUnresolved if unset
    actual = **FETCH[meta["fetch"]]**(self, identity, scope, meta)
    if actual is None:                                          # ---- CREATE
        body = meta["models"]["create"].model_validate(_present(desired))
        if check_mode: return <predicted created, no write>
        resp = self.create(body=body, **_path_args(scope))
        after = **MATERIALIZE[meta["materialize"]]**(self, resp, identity, scope, meta)
        return SyncResult(True, "created", None, _wire(after), ...)
    d = diff(desired, actual)                                   # engine core
    if not d.changed: return <unchanged no-op>
    if check_mode: return <predicted updated, no write>
    resp = **MUTATE[meta["mutate"]]**(self, desired, actual, d, meta)   # raw response
    after = **MATERIALIZE[meta["materialize"]]**(self, resp, identity, scope, meta)
    return SyncResult(True, "updated", _wire(actual), _wire(after), d, ...)

absent(desired_or_identity, check_mode):
    if meta["singleton"]: raise AbsentNotSupported(...)
    identity, scope = _extract_identity(desired_or_identity, meta)
    actual = FETCH[meta["fetch"]](self, identity, scope, meta)
    if actual is None: return <unchanged no-op>
    if not check_mode: self.delete(id=actual.id)
    return SyncResult(True, "deleted", _wire(actual), None, ...)

fetch(**identity_and_scope):     # the public primitive; splits kwargs, calls the strategy
    identity, scope = _split(identity_and_scope, meta)
    return FETCH[meta["fetch"]](self, identity, scope, meta)
```

Create and update both feed their response through the SAME `materialize` strategy,
so id-envelope handling (F3) is written once. `direct` returns the response as-is;
`get_after_write` re-GETs by id.

### 5.3 Seam contracts (Protocols in `base.py`)

Each strategy is a plain callable; the seams are Python `Protocol`s so a custom
strategy (§5.5) is duck-typed, never subclassed:

```python
class FetchStrategy(Protocol):
    def __call__(self, res, identity: dict, scope: dict, meta: dict) -> Any | None: ...

class MutateStrategy(Protocol):
    def __call__(self, res, desired, actual, diff, meta: dict) -> Any: ...   # raw response

class MaterializeStrategy(Protocol):
    def __call__(self, res, response, identity: dict, scope: dict, meta: dict) -> Any: ...
```

`base.py` also holds the three registries the orchestrator resolves at call time:

```python
FETCH: dict[str, FetchStrategy] = {}
MUTATE: dict[str, MutateStrategy] = {}
MATERIALIZE: dict[str, MaterializeStrategy] = {}
```

Each vendored strategy module registers its callable under its name
(`FETCH["list_scan"] = list_scan`), or `engine.py` imports the vendored set and
builds the registry from it. The orchestrator looks up `FETCH[meta["fetch"]]` /
`MUTATE[meta["mutate"]]` / `MATERIALIZE[meta["materialize"]]`.

### 5.4 The baked `_idempotency` classvar

Baked at build time from `sdk.yml` (§6) + the IR. All field names are **wire keys**
(the `by_alias=True` names), matching the diff's normalization plane. It now carries
the three **strategy-name keys** alongside the data the strategies read:

```python
_idempotency: ClassVar[dict[str, Any]] = {
    # natural key; a LIST — composite identity falls out of the general mechanism
    "identity": ["name"],
    # optional scope group; None for products/resources without one (prisma-browser)
    "scope": {"fields": ["folder", "snippet", "device"], "rule": "exactly_one"},
    # per-operation live model classes (F4): create/update/read may all differ
    "models": {"create": Addresses, "update": Addresses, "read": Addresses},
    # the comparable universe: create/update INPUT schema field wire-keys (F4)
    "input_fields": ["name", "description", "ip_netmask", "tag", "folder", "snippet", "device"],
    # excluded from diff on top of scope: sdk.yml read_only/computed + the id field
    "server_only": ["id"],
    # wire key + attr of the server id, for get-after-write + URL routing (F3)
    "id_field": {"wire": "id", "attr": "id"},
    # list-typed fields forced ORDER-SENSITIVE (default is order-insensitive)
    "order_sensitive": [],
    # lifecycle shape
    "singleton": False,
    # the wrapper verb the mutate strategy calls (F9)
    "update": {"verb": "replace"},
    # --- the three baked strategy names (auto-selected; §5.5) ---
    "fetch": "list_scan",         # | "list_filter" | "get"
    "mutate": "put_rmw",          # | "patch_minimal"
    "materialize": "direct",      # | "get_after_write"
    # tuning consumed by the fetch strategy
    "fetch_opts": {"page_limit": 200, "hydrate": True},
}
```

Derivation, per source (the three strategy rows are the automatic selection — §5.5):

| Key | Source |
|---|---|
| `identity` | `sdk.yml` annotation, or inferred (`name` present in the create-input model → `["name"]`); fail-loud on ambiguity (§8.3) |
| `scope` | `sdk.yml` (`idempotency.defaults.scope` / per-resource); absent → `None` |
| `models` | IR: the create / update / read live model classes for this object's bindings (F4) |
| `input_fields` | IR: the union of the create+update body models' `FieldInfo` sets, wire keys via the models' aliases |
| `server_only` | the resolved `id` field ∪ `sdk.yml` `read_only:` + `computed:` |
| `id_field` | wire key + python attr of `id` on the read model (F3) |
| `order_sensitive` | `sdk.yml` per-resource annotation |
| `singleton` | `sdk.yml` `singleton: true` (auto-detected candidates — no create/delete/list — reported for confirmation) |
| `update.verb` | IR: the wrapper verb name of the update binding (`replace` for PUT, `update` for PATCH) (F9) |
| **`fetch`** | `"list_scan"` default (F1); `"list_filter"` only when opted-in AND every identity field is a list query param; `"get"` for singletons |
| **`mutate`** | `"patch_minimal"` when a `patch` sub-verb exists on the update binding, else `"put_rmw"` (F9) |
| **`materialize`** | `"direct"` when the mutating verb's return model equals the read model, else `"get_after_write"` (F3) |

The literal is computed in `build_wrapper_context` (`generator/sdk/wrapper.py`)
alongside `bindings_literal` — same producer, same render path, same drift-safety
argument: the engine executes **from** this data (including the strategy names), so
consumers reading it cannot disagree with behavior.

### 5.5 Automatic selection, union-vendoring, and the custom escape hatch

**Selection is automatic by default.** The Phase-0 producer derives each family's
variant from the IR / response shape / sub-verbs (the three strategy rows in §5.4)
and bakes the NAME into `_idempotency`. A user's `sdk.yml` entry stays ergonomic
(`address: {}`). Two override levels exist as an **escape hatch, not routine**, and
resolve in this order per family — **`resources.<name>.<family>` →
`defaults.<family>` → auto-derived**:

- **per-product / per-subpackage** — `idempotency.defaults.{fetch,mutate,materialize}`
  sets a blanket default for every resource in that block (e.g. a product whose
  whole API supports name filters → `defaults.fetch: list_filter`);
- **per-resource** — the same fields on `IdempotencyResource` (§6) override the
  default for a single diverging resource.

Both accept a built-in variant name or a custom module (`type: ./path.jinja` /
`hooks.py`). Today both products leave `defaults` strategy fields unset — every
resource uses auto-selection; the levels exist so a future product can opt in
without per-resource annotation.

**Union-vendoring.** `render.vendor()` (extended) vendors `engine.py` + `base.py`
plus **only the strategy modules referenced** across the product's opted-in
resources — unlike `pagination`, which is one-per-product:

- prisma-access → `fetch/list_scan` + `mutate/put_rmw` + `materialize/direct`.
- prisma-browser → `fetch/list_filter` (+ `fetch/get` for singletons) +
  `mutate/patch_minimal` + `materialize/get_after_write`.

**Custom / novel per product.** A product needing a variant none of the built-ins
provide supplies a strategy module through the existing custom-component escape
hatch (`type: ./path.jinja`) or registers a callable in `hooks.py`; the
`_idempotency` metadata names it; the registry resolves it — **no shared-engine
edit, no fork**. This is the documented extensibility path, and the property
(pan-scm's per-module duplication avoided) that motivates ADR-0004.

### 5.6 Prototype mapping (translate the validated logic, don't reinvent)

Each strategy reproduces a proven branch of the throwaway prototype
(`prototypes/sync-engine/`, 17/17 + 13/13 live):

| Strategy / piece | Validated prototype source |
|---|---|
| orchestrator `apply`/`absent`/`diff`/`_extract_identity` | `engine.py` `apply`/`absent`/`diff`/`_extract_identity` |
| fetch/`list_scan` | `engine.py` `fetch()` list_scan branch (not_found catch, `page_limit`, exact match) |
| fetch/`list_filter` (+hydrate) | `run_prisma_browser.py` `fetch()` (list + match + GET) |
| fetch/`get` (singleton) | `engine.py` `fetch` get-path (404 → None) |
| mutate/`put_rmw` | `engine.py` `_build_update_body` PUT branch |
| mutate/`patch_minimal` | `engine.py` `_build_update_body` PATCH branch; `run_prisma_browser.py` `apply` PATCH |
| materialize/`direct` | `run_prisma_access.py` (response is the object) |
| materialize/`get_after_write` | `run_prisma_browser.py` `apply()` create/patch GET-after (~lines 83–97) |

All §0 findings still hold; they now land INSIDE specific strategies — F1/F2 in
fetch/`list_scan`, F3 in materialize/`get_after_write`, F9 in `mutate` — while F5's
per-field projection stays an engine-core `_normalize` hook (§7).

### 5.7 Behavior notes (unchanged from the validated design)

- **mutate/put_rmw preserves unmanaged server fields** by construction: the body is
  seeded from the fetched actual, only user-set desired fields overlay it, and the
  identity (`id`) routes to the URL via the wrapper's normal binding dispatch
  (`requires: ["id"]`). This matches pan-scm-sdk's PUT-with-id-popped pattern, but
  derived from data, not hand-written per module. It is the only mutate strategy
  prisma-access needs (zero PATCH ops).
- **mutate/patch_minimal** sends only `Diff.changes` — the natural fit for
  prisma-browser's 12 PATCH ops.
- **materialize** turns the mutation response into `after`: `direct` when the write
  echoes the object (prisma-access), `get_after_write` when it is an id-only
  envelope (prisma-browser, F3) — one GET, written once for both create and update.
- **fetch/list_scan** absorbs F1/F2: `self.list(all_pages=True, ...)` +
  client-side exact-match; empty set OR `NotFoundException` → `None`;
  singleton `get` maps `NotFoundException` from the errors component → `None`.
- `check_mode` computes the full `SyncResult` **without any write**, and runs the
  existing `_serialize` path to constructively validate the would-be payload (the
  same seam the CLI's `--dry-run` uses today, `resource.py.jinja` `_serialize`).
  This is the mechanism a future CLI `--dry-run apply` reuses.

### 5.8 resource.py.jinja wiring

`resource.py.jinja` changes minimally: an opted-in object's class gains the mixin
and the classvar, exactly mirroring `_bindings`:

```python
from .idempotency import SyncMixin        # only when the (sub)package opts in

class AddressResource(SyncMixin):
    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {...}   # unchanged
    _idempotency: ClassVar[dict[str, Any]] = {...}                 # NEW, baked
```

A non-opted-in object renders exactly as today (no base class, no classvar, no
import). The orchestrator calls only the wrapper's own public verbs
(`self.create/get/list/update/replace/delete`) and the existing `_serialize` seam —
it never reaches the raw `*Api`, so multi-binding dispatch, enum coercion,
pagination, and retry all apply for free.

## 6. Change 2 (config side) — the `sdk.yml` idempotency block (ADR-0003)

### 6.1 Schema

New pydantic models in `src/phantasos/config.py`, wired through `productconfig.py` (`ProductConfig.idempotency` for single-spec; `SubPackage.idempotency` for federated — the same split as `operations:`):

```python
class ScopeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fields: list[str]
    rule: Literal["exactly_one"] = "exactly_one"

class IdempotencyResource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    identity: list[str] | None = None      # None -> infer (fail-loud on ambiguity)
    read_only: list[str] = []
    computed: list[str] = []
    order_sensitive: list[str] = []        # list fields compared order-sensitively
    singleton: bool = False
    scope: ScopeSpec | None = None         # per-resource override of defaults.scope
    sync: bool = True                      # False -> CRUD primitives only, no apply/absent
    # Strategy overrides — ESCAPE HATCH, not routine. Each family's variant is
    # auto-selected by the Phase-0 producer (§5.5) and baked into `_idempotency`;
    # set one only to force a non-default variant, or name a custom module
    # supplied via `type: ./path.jinja` / `hooks.py`. None -> auto-derive.
    fetch: Literal["list_scan", "list_filter", "get"] | str | None = None
    mutate: Literal["put_rmw", "patch_minimal"] | str | None = None
    materialize: Literal["direct", "get_after_write"] | str | None = None

class IdempotencyDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    scope: ScopeSpec | None = None
    read_only: list[str] = []
    computed: list[str] = []
    # PER-PRODUCT / PER-SUBPACKAGE strategy defaults — apply to every resource in
    # this block unless a `resources.<name>` entry overrides. Unset -> auto-select.
    # Precedence per family: resources.<name>.<family> > defaults.<family> > auto.
    fetch: Literal["list_scan", "list_filter", "get"] | str | None = None
    mutate: Literal["put_rmw", "patch_minimal"] | str | None = None
    materialize: Literal["direct", "get_after_write"] | str | None = None

class IdempotencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    defaults: IdempotencyDefaults = Field(default_factory=IdempotencyDefaults)
    # keyed by the classified wrapper object attr (the `client.<object>` name),
    # same vocabulary as `operations:` resources
    resources: dict[str, IdempotencyResource] = Field(default_factory=dict)
```

Semantics:

- **Absent block → generate exactly as today** (the whole feature is gated on it).
- **Block present → each resource LISTED under `resources:` opts in; unlisted resources stay on CRUD primitives only** (no sync surface, no build failure). Opt-in is per-listed-resource — the shipped, conservative model, which lets a catalog be rolled out incrementally by adding resource keys. For a *listed* resource, identity is inferred where obvious (`name` in the create input schema); a listed resource whose identity cannot be inferred and that supplies no `identity:` annotation **fails the build loudly** (naming the resource, demanding an `identity:` or `sync: false` — never a silently broken `apply`). `sync: false` explicitly keeps a listed resource on CRUD primitives only (used to record "considered, not syncable" with a reason). Listing a resource that is not CRUD-complete (missing a list op for identity resolution, no update verb, etc.) also fails the build.
- Keys under `resources:` are validated against the built wrapper objects (same fail-loud posture as `validate_override_keys` for `operations:`).
- Field names in the block are **wire keys** (the spec's property names), matching the diff plane.
- **Strategy selection is auto-derived** (ADR-0004 / §5.5): the Phase-0 producer picks each resource's `fetch`/`mutate`/`materialize` variant from the IR (fetch strategy per F1, mutate per sub-verbs/F9, materialize per response shape/F3) and bakes the NAME into `_idempotency`. The `fetch`/`mutate`/`materialize` fields above are an escape hatch — leave them unset for the common case. The generator then vendors the **union** of the strategy modules the opted-in resources reference.

### 6.2 prisma-access example (with scope)

Block style only, per the repo YAML rule — this sits alongside the existing per-sub `operations:` in `products/prisma-access/sdk.yml`:

```yaml
subpackages:
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
        address_group:
          order_sensitive:
            - static
        tag: {}
        # server-id-keyed; no natural key -> primitives only, explicit and loud
        auto_tag_action:
          sync: false
  - slug: network_services
    spec: openapi/network-services.yaml
    idempotency:
      defaults:
        scope:
          fields:
            - folder
            - snippet
            - device
          rule: exactly_one
      resources:
        bgp_routing:
          singleton: true
```

(`address: {}` = "inferred identity `[name]`, defaults apply" — the common case covering ~130–140 of the ~156 prisma-access resources per the feasibility scan. Empty mappings stay flow per the YAML rule.)

### 6.3 prisma-browser example (no scope)

```yaml
idempotency:
  defaults:
    read_only:
      - id
      - createdAt
      - updatedAt
  resources:
    user_group: {}
    device_group: {}
    application:
      identity:
        - type
        - name
    application_plugin:
      sync: false
```

No `scope` anywhere: the scope group is empty, every scope step in the engine is a no-op, and no scope validator is emitted — scope is a **generic optional annotation**, not an SCM assumption baked into the engine. `application` shows composite identity; `user_group` gets `fetch: "list_scan"` baked automatically (no name list-filter in the spec — IR-derived, not authored), and prisma-browser's PATCH + id-envelope shape bakes `mutate: "patch_minimal"` + `materialize: "get_after_write"` (§5.5). `id` must be declared `read_only` here because prisma-browser never marks it `readOnly` (which is also why `input_fields` — not `readOnly` — is the comparable universe).

## 7. Diff semantics

The **comparable set** for one `diff(desired, actual)` call is:

```
input_fields  ∩  user-set(desired)  −  scope.fields  −  server_only
```

- `input_fields`: what the user *can* set — the create/update input schema, from the IR. Keying off input schemas (not `readOnly`) is load-bearing for prisma-browser (§3).
- `user-set(desired)`: `desired.model_dump(by_alias=True, exclude_unset=True)` — **unset desired fields are unmanaged**: not diffed, never reverted (standard "manage what you declare"; the accepted trade-off from the feasibility report §7).
- scope and server-only fields are never drift.

Both sides are normalized to **wire form** before comparison:

```
_normalize(value, field, meta):
    model      -> model_dump(mode="json", by_alias=True), then recurse per key
    enum       -> its wire value
    list       -> [_normalize(v) for v in value]
                  then, unless field in meta["order_sensitive"]:
                      canonical sort by json.dumps(v, sort_keys=True)
                  (order-INSENSITIVE by default; sdk.yml opts a field into order)
    scalar     -> as-is (mode="json" already stringified dates etc.)

diff(desired, actual):
    d, a = wire(desired, exclude_unset=True), wire(actual)
    changes = {}
    for key in comparable_set:
        if _normalize(d[key], key) != _normalize(a.get(key), key):
            changes[key] = {"before": a.get(key), "after": d[key]}
    return Diff(changed=bool(changes), changes=changes)
```

Nested models recurse; nested lists inherit the parent field's order annotation. `Diff.changes` records the **un-normalized wire values** (what will actually be sent / what the server actually holds), so `before`/`after` in results stay faithful; normalization is only the equality plane.

## 8. Awkward shapes

### 8.1 Singletons (`singleton: true`, identity `[]`)

Config-blob resources (prisma-access `bgp_routing`, `shared-infrastructure-settings`, device `*-settings`; the feasibility scan counts ~8–15). Lifecycle: **always-update** —

- `fetch()` uses the object's get binding (no identity args); a 404 (`NotFoundException` from the errors component) still maps to `None` defensively, but the expected steady state is "always present".
- `apply` never takes the create branch (no create op exists in `_bindings`); it is fetch → diff → update/no-op.
- `absent` raises `AbsentNotSupported` — a singleton has no delete lifecycle. This is a contract signal to consumers (the Ansible layer maps such resources to update-only modules), not an error path to handle silently.

### 8.2 Composite identity

`identity` is a **list**, so composites fall out of the general mechanism with no special casing: prisma-browser's `application` declares `identity: [type, name]`; `_extract_identity` pulls both from `desired`; `fetch` passes both to the lookup (`type` is a real query/path param on the list/get bindings — the wrapper's `_select` routes it); the exact-match re-filter closes any gap. Update routes by whatever the update binding `requires` — typically `id` (and `type`) taken **from the fetched actual**, never from the user.

### 8.3 No resolvable identity

A **listed** resource (one named under `resources:`) with no `name`-like input field, no `identity:` annotation, and no `sync: false` → **the build fails** listing the resource as "needs identity annotation" (mirroring the `operations:` anchorless-op gate in `build_wrapper_context`). The resolution is a human decision recorded in `sdk.yml`: annotate an identity (e.g. `threat_id` for the signature resources, or `identity: []` for a per-scope singleton blob), or declare `sync: false` to ship CRUD primitives only. Nothing is silently shipped without a working `apply`. (An *unlisted* resource never reaches this gate — it simply keeps CRUD primitives, per §6.1.)

## 9. Change 3 — the injectable-token auth seam

In `components/auth/scm_oauth.py.jinja`, additive:

```python
class _ProviderTokenSource:
    """Duck-types TokenManager's `.token()` for a caller-owned token."""
    def __init__(self, provider: Callable[[], str]) -> None:
        self._provider = provider
    def token(self) -> str:
        return self._provider()


def api_client_from_token(
    token: str | Callable[[], str], *, host: str = DEFAULT_BASE_URL
) -> ApiClient:
    provider = (lambda: token) if isinstance(token, str) else token
    cfg = {{ config_class_name }}(token_manager=_ProviderTokenSource(provider), host=host)
    return ApiClient(cfg)        # federated: _BearerApiClient(cfg)
```

and on the facade `Client` (`components/facade/client.py.jinja`), beside `from_env`/`from_credentials`:

```python
@classmethod
def from_access_token(cls, token: str | Callable[[], str], *, host: str = DEFAULT_BASE_URL) -> "Client":
    return cls(api_client_from_token(token, host=host))
```

Why this is small and correct: `{{ config_class_name }}.access_token` is already a **property** delegating to `self._token_manager.token()`, and OAG's request path reads that property fresh on every request. `_ProviderTokenSource` satisfies the same one-method protocol, so a callable provider is consulted per request — the caller (the future httpapi plugin, which catches a 401, refreshes its token, and retries) needs **no** SDK hook to rotate tokens. The SDK's own OAuth machinery (`TokenManager`, grant, scope/secret) is simply not constructed on this path. For the **federated** build the same pair lands in the shared `<package>/_auth.py` (`configuration_from_token`, mirroring `configuration_from_credentials`) and the composer `Client` gains the same `from_access_token` classmethod building the one shared `SdkConfiguration` — the rev-5 single-runtime architecture is unaffected.

pan-scm-sdk's pre-supplied `access_token` path validates the demand for this seam; ours differs by accepting a **provider**, which is what makes external refresh transparent instead of requiring client reconstruction.

## 10. Scope handling (generic, data-driven)

Scope is declared, never assumed:

- **Declared** (`scope: {fields: [folder, snippet, device], rule: exactly_one}`) — prisma-access only. Then, in one data-driven code path: scope fields are part of the **fetch lookup key** (passed as list-filter params alongside `name`), **excluded from diff** (a container move is not drift — it's a different object), **carried from the fetched actual** onto PUT bodies (never dropped, never taken from a stale desired), and validated below.
- **Absent** (prisma-browser) — `meta["scope"] is None`, every scope step is a no-op, no validator is emitted. The engine has no SCM knowledge; it interprets the annotation or skips.

**Symmetric mutual-exclusion validator (in scope for this spec).** When a scope group is declared, the generator emits a pydantic `model_validator(mode="after")` on **all mutating models — create AND update** — enforcing the rule (`exactly_one`: exactly one of the scope fields set). **⚠ Correction (F7): live testing shows the SERVER already rejects 0-/2-container bodies (400)**, so this validator is **fail-fast UX / defense-in-depth, not a correctness gap the server misses** — the "malformed update slips to the server" rationale below is superseded. Still worth generating for a clearer, earlier error, but it is not load-bearing for correctness. Mechanically this is a new generation-time patch pass in `generator/sdk/patches.py` (`patch_scope_validators(models_dir, scope)`, a sibling of `patch_oneof_unwrap_serializer` etc.), applied to the input models the IR identifies as create/update bodies, gated on the idempotency config. This closes a real correctness gap in the reference project: **cdot65/pan-scm-ansible validates the container on Create only**, so a malformed update slips to the server. Background: the federated build's `flatten_scm_bodies` preprocess (see `.agents/context/sdk-generator.md`) deliberately drops the spec's `oneOf` exactly-one composition to recover the payload fields — this validator restores the lost constraint on the client side, symmetrically. Because SCM reuses one schema for requests and responses, the validator carries a **server-echo guard**: it is skipped when the instance carries a server-assigned `id` (a fetched/echoed object — e.g. a predefined object with no container — must never fail deserialization); user-authored mutation bodies never set the readOnly `id`, so they are always enforced.

## 11. Rollout, opt-in, compatibility

- **Additive and opt-in at every level.** No `idempotency:` block → no `extras/idempotency/` package (engine, base, or any strategy module), no mixin, no classvar, no validators, no new client constructor beyond `from_access_token` (which is emitted whenever the auth component is — it is credential-handling, not idempotency). Existing products regenerate byte-identically until their `sdk.yml` opts in.
- **Per-resource opt-out** via `sync: false`; per-resource shape overrides via the `resources:` entry.
- Rollout order follows the feasibility roadmap: prisma-browser first (smaller, fiddlier — exercises PATCH-minimal, `list_scan`, composite identity, no-scope), then prisma-access (exercises scope, PUT-only, federation breadth).
- **Docs:** `.agents/context/sdk-generator.md` narrative + generated blocks updated when this lands (`uv run nox -s context`); the generated SDK's MkDocs guides gain a sync-operations page (wrapper-surface, like the CRUD guide) — deferred to the plan.
- **Noted future consumers, not built here:** CLI `apply` / `--if-changed` (reads the same `SyncResult`), and the Ansible `module_utils` engine (a thin adapter over `apply`/`absent`/`SyncResult`).

## 12. Testability & verification

The engine is deliberately **unit-testable inside the SDK**, where the models and aliases live (feasibility report §5, tier 3):

- **Offline engine unit tests** (extend `tests/test_sdk_wrapper.py` / a new `tests/test_sdk_sync.py`): drive the orchestrator (`SyncMixin`) and **each strategy module independently** against a stub resource carrying a hand-built `_idempotency` classvar and canned wrapper verbs — orchestrator-core: normalization (enum/nested/list order-insensitivity + `order_sensitive` override), comparable-set arithmetic (unset-unmanaged, scope/server-only exclusion), check_mode prediction, singleton/`AbsentNotSupported`, composite identity, `IdentityUnresolved` on missing identity; per strategy: fetch/`list_scan` (>1 match, empty/404→None), fetch/`list_filter`(+hydrate), mutate/`put_rmw` (seed+overlay+id-drop) vs mutate/`patch_minimal` (changed-only in the patch model), materialize/`direct` vs materialize/`get_after_write` (id-envelope → GET). The stub is scaffolding around the real SUT (the engine + the strategies), not a mock of the prisma-browser API boundary — consistent with the repo test policy.
- **Baking tests**: `build_wrapper_context` produces the expected `_idempotency` literal from sdk.yml + a real inventory (strategy auto-selection from sub-verbs, `list_filter` vs `list_scan` from query params, fail-loud on unresolvable identity, `resources:` key validation).
- **Real-artifact ring**: the built prisma-browser SDK exposes `apply`/`fetch`/`diff` with the specced signatures; the scope validator rejects two-container / zero-container mutation bodies on a built prisma-access model and accepts server echoes.
- **Live gate** (`uv run nox -s live`, skips without credentials): the idempotency quartet on at least one real resource per product — create→`changed`, re-apply→`not changed` (the idempotency proof), modify→`changed` with a correct `Diff`, absent→`changed` — the only tier that proves identity + diff correctness against the tenant, per the phase-boundary policy in `CLAUDE.md`.

## 13. Risks & open questions

- **Server-normalized values causing false drift** (e.g. the server lowercases, reorders, or canonicalizes a value the user spelled differently). The normalization plane (§7) covers the known cases (enums, list order, JSON scalarization); residual cases surface fast in the live quartet and are fixed by widening `_normalize` or annotating the field `computed`. Bounded, observable, and the annotation layer exists for exactly this.
- **`list_scan` on large tenants** (prisma-browser UserGroups, rules/sections): list-all-and-match reuses the wrapper's `all_pages=True` pagination but is O(collection). Flagged per-resource at build time (the baked `fetch.strategy` is inspectable); acceptable for the affected small collections, revisit if a large unfiltered collection ever opts in.
- **Scope-validator server-echo guard** (§10): the "skip when `id` is set" heuristic must be confirmed against real prisma-access responses in the first implementation phase (are there echoed objects with neither `id` nor a container?). If the guard proves too coarse, fall back to enforcing the rule in the engine's `_build_*_body` path plus the validator on create-only input models — the symmetric guarantee then lives in the engine. Settle at plan time with real payloads.
- **PUT merge vs server-side required fields**: read-modify-write seeds from the actual, so required-on-PUT fields the user never set are present by construction; the preprocess `relax_readonly_required` already prevents the inverse problem on create. Verified by the live quartet's modify leg.
- **Open (non-blocking), settle at plan time:** the vendored layout is now a package, `extras/idempotency/` (ADR-0004), not a single `extras/sync.py`; whether `absent` also accepts bare identity kwargs (`absent(name=..., folder=...)`) in addition to a model — the contract above says model-or-identity object, kwargs would be sugar; whether `SyncResult` should carry the rendered request preview under `check_mode` (the `_serialize` output) for CLI `--dry-run` display.

## 14. Glossary

- **Sync operation (`apply` / `absent`)** — the high-level SDK facade operation that makes a resource match a desired state idempotently: fetch → diff → create/update/delete/no-op. `apply` ensures present; `absent` ensures deleted. (Not "reconcile"/"converge".)
- **Desired** — the caller-supplied target state (a typed model); partial by nature — only the fields the user set are managed.
- **Actual** — the current server-side state, as returned by `fetch`.
- **fetch** (primitive) — look up one existing resource by natural identity (+ scope); returns `Model | None`, absorbing the raw 404 / empty-list internally. Distinct from `get` (get-by-server-id) — no exception-as-control-flow for existence.
- **diff** (primitive) — pure comparison of desired vs actual over the comparable set (§7), returning a typed `Diff`.
- **`Diff`** — frozen; `.changed: bool`, `.changes: {wire-key: {before, after}}`; empty/`changed=False` when in sync.
- **`SyncResult`** — frozen; `changed`, `action: created|updated|deleted|unchanged`, `before`/`after` wire-key dicts (+ typed models), `diff`. Under `check_mode`, computed from the planned change with no write.
- **Identity** — the natural key that selects a resource (`name`, or a composite list like `[type, name]`); distinct from the server-assigned `id`/uuid.
- **Scope** — a generic, optional, per-resource container annotation (`scope: {fields: [...], rule: exactly_one}`; SCM instance: `folder`/`snippet`/`device`). Part of the fetch key, excluded from diff, carried from actual on PUT, and enforced symmetrically on mutating models. Empty group → every scope step is a no-op.
- **Comparable set** — `input_fields ∩ user-set(desired) − scope − server_only`; the only fields diff may report.
- **Update payload** — create: body from desired. PATCH-minimal: only `Diff.changes`. PUT read-modify-write: actual seeded, user-set desired overlaid, identity→URL, unmanaged server fields preserved. Strategy auto-selected from IR sub-verbs.
- **Idempotency engine** — the thin orchestrator (`SyncMixin`) shipped as the new `idempotency` SDK component, interpreting the per-resource `_idempotency` classvar baked by the generator (the `_bindings` idiom) and delegating the varying steps to **composable strategy components** — `fetch` (`list_scan`/`list_filter`/`get`), `mutate` (`put_rmw`/`patch_minimal`), `materialize` (`direct`/`get_after_write`); the generator vendors the union of the strategies its opted-in resources reference (ADR-0004, §5). Methods live on the resource wrapper (`client.<res>.apply(...)`).
- **Sync strategy** — a named, swappable component variant in one of the three families (fetch / mutate / materialize), selected per resource (auto-derived, overridable) and vendored as its own module; the orchestrator resolves it through a registry at call time.
- **Injectable-token seam (`from_access_token`)** — client construction from an externally-owned `str | Callable[[], str]` token source, wired to the existing `access_token` pull-model property; the caller owns refresh and 401-retry.
- **Idempotency quartet** — the live gate per resource: create→changed, re-apply→not changed, modify→changed, absent→changed.
