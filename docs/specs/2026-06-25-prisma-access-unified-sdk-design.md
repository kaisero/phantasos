# Prisma Access — unified multi-spec SDK: design spec

- **Date:** 2026-06-25 (rev 3: 2026-06-26; rev 4: 2026-06-26; rev 5: 2026-06-26; rev 6: 2026-06-26; rev 7: 2026-06-26)
- **Branch:** `feature/prisma-access-sdk` (off `develop` @ `e0e0561`)
- **Status:** Design spec, **rev 7** — rev-3 architecture pivot (merge → **federated sub-packages**), rev-4 auth simplification (bearer at a spec-agnostic transport hook), rev-5 single shared runtime (one `prisma_access._runtime` + one `Configuration` + one pool + N thin `ApiClient` handles), rev-6 federated docs site (one distribution MkDocs site), and **rev-7 CLI forward-compatibility** (composer exposes a `_SUBPACKAGES` introspection registry so the future CLI — out of scope here — ties in cleanly). Feasibility-validated against real code + the live OAG jar. No code yet. Awaiting the same two-expert review, then maintainer review.
- **Scope:** **SDK generation only** (no CLI). In scope: the runtime SDK **and** its opt-in MkDocs site (federation-aware, D9). The emitted SDK must stay CLI-introspectable later, but no CLI work is in scope.
- **North star:** a Unified SDK that **feels as consistent as possible while retaining every feature in the OAS specs.** In rev 3 this means: **one navigable distribution** (`prisma-access-sdk`, `import prisma_access`) where **each spec is its own sub-package** (`prisma_access.objects`, `prisma_access.posture`, …), all reached through **one composing client with one shared credential** — *consistent surface* = uniform per-sub-package shape + one entry point + one auth; *complete payload* = each spec fully and faithfully represented in its own namespace.

---

## 0. Architecture pivot in rev 3 (why this replaces rev 2)

**Maintainer decision (walk-back of rev-2 D2):** do **not** merge the 12 specs into one OpenAPI document. A single merged package would cluster ~1000 models + 784 ops into one flat, un-navigable namespace. Instead, **generate one Python distribution containing one sub-package per spec** — `prisma_access.objects`, `prisma_access.posture`, `prisma_access.security_services`, … — uniqueness and navigability keyed by package.

This is essentially the original "Option B" (per-spec → compose), which rev 2 down-ranked on *merge* grounds. The maintainer's product judgment on navigability overrides that — and feasibility validation (below) shows the pivot is **simpler**, not harder: most of rev 2's hard problems dissolve.

**Dissolved (no longer in scope):** the merge step, cross-spec schema-collision dedupe + fail-loud drift guard, OAS version unification (the 3.0.3 / `nullable`-loss CRITICAL), `$ref` rewriting, OR-merging of `security`, and the "which gateway prefix to fold" ambiguity. Each spec is generated in isolation, so same-named schemas (`generic_error`, the 4 rev-2 conflicts) simply live once per sub-package — expected, not a conflict.

**Becomes the work (orchestration, not tooling):** an N-sub-package build loop, a multi-spec config model, a vendored-once shared `TokenManager`, and a thin top-level composing client. All validated feasible.

**Rev-4 auth refinement (2026-06-26, maintainer-confirmed):** auth is identical across all 12 specs and **every endpoint sits behind it**, so bearer injection moves out of OAG's per-spec `security` machinery into the **transport layer** — the vendored `scm_oauth` ApiClient (`_BearerApiClient`) unconditionally attaches `Authorization: Bearer <pull-model token>`. This **dissolves posture's `inject_security` spec mutation** (the last auth-side spec surgery) and removes any dependence on the 11 divergent scheme names matching per sub-package. Per-spec deltas (ztna path, region/tenant headers) stay decoupled as declarative `default_headers` config. See D4 / §5.

**Rev-5 single shared runtime (2026-06-26, maintainer decision — overturns rev-3 F6):** rev 3 accepted **N copies of the OAG runtime** (~25k LOC + 12 `urllib3` pools) as YAGNI. Re-tracing the built `prisma-browser-sdk` shows that was overstated: the **only** semantic package-binding in the entire runtime is one line — `klass = getattr(prisma_browser.models, klass)` (`api_client.py:455`). `configuration.py`/`rest.py`/`exceptions.py`/`api_response.py` are package-agnostic; models have **zero** runtime coupling. So the runtime is emitted **once** under `prisma_access._runtime`, that one line is abstracted to `getattr(self.models, klass)`, and the composer builds **one** `Configuration` + **one** connection pool + **N thin `ApiClient` handles**, each tagged `handle.models = prisma_access.<slug>.models`. Collision-free by construction (each handle resolves only its own sub-package's response models). The 642-file **models tree stays federated** (the navigability reason for the pivot) — runtime-sharing is orthogonal to it. Cost: a bounded, mechanical generation-time import-rewrite pass (the pass F6 deferred). See D8 / §1 F6 / §5 / §8.

**Rev-6 federated docs site (2026-06-26, maintainer decision):** the SDK docs generator is **package-singular** — `build_docs_context` imports `{package}.extras.facade`/`.models` (`docs.py:202-206`), `gen_ref_pages.py.jinja` walks one `{package}.extras.facade._WRAPPERS` + one `{package}/models` tree, and `DocsConfig` carries one `showcase_resource`. The federated root `prisma_access` holds no facade/models (those are one level down), so the machinery does **not** work as-is. The *rendering* machinery (mkdocstrings of `<Object>Resource` wrappers + model modules, the IR-driven showcase, the guides) is fully reusable — it just has to **run per sub-package**. Decision: **one distribution MkDocs site** — `gen_ref_pages` loops the sub-packages so the API Reference covers **all 12** (grouped by sub-package, auto-built via literate-nav `SUMMARY.md`); the CRUD/auth/pagination **guides** teach **one representative showcase** (`client.objects.address`). The runtime SDK itself (facade, pagination, retry, errors, `_lenient`, `_about`) is already per-sub-package and needs **no** extra wiring beyond rev 5. See D9 / §6.1 / §8.

**Rev-7 CLI forward-compatibility (2026-06-26, maintainer decision — CLI itself out of scope):** the CLI generator (`phantasos cli build`) consumes the **built SDK artifact** through a per-package introspection contract — `introspect`/`cli_operations` read `extras.facade._RESOURCES`/`_WRAPPERS`, `build_model_registry` the model schemas, and the emitted Typer tree is verb-first with a **nestable `typer_path` list** (`app.py.jinja:82-91`). Federation **preserves that contract exactly**: each sub-package keeps its own `_WRAPPERS`/`_RESOURCES` (F2), so `cli_operations("prisma_access.objects", …)` works per sub-package unchanged, and `client.objects.address.create()` maps 1:1 to a CLI command path. The only future CLI-side work (deferred) is to **loop the sub-packages** (like docs) and add **one command level** for the sub-package (the `typer_path` list already nests). To make both docs and the future CLI enumerate sub-packages by **introspecting the artifact, not re-reading `sdk.yml`**, the composer exposes a **`_SUBPACKAGES` registry** (slug → sub-package facade `Client`), mirroring `_WRAPPERS`/`_RESOURCES`. **Recorded (non-binding) lean for the future CLI tree:** verb-first `prisma-access <verb> <sub-package> <object>` (`typer_path = [verb, subpackage, object]`), extending today's `_VERBS` grouping — the SDK supports resource-first equally. See D10 / §6.2. **No CLI is built this round.**

---

## 1. Feasibility validation (against real code + the live OAG jar)

Three read-only reviewers; key claims proven by running the **real cached OAG 7.22.0 jar** and inspecting the built `../prisma-browser-sdk`.

**F1 — Dotted `--package-name` → nested sub-packages. PROVEN.** Running OAG 7.22.0 with `--package-name prisma_access.objects` emits `prisma_access/objects/{api_client,configuration,rest,exceptions,api_response}.py`, `prisma_access/objects/{api,models}/…`, plus an **empty** parent `prisma_access/__init__.py`. A second run (`--package-name prisma_access.posture`, same `-o`) coexists; it re-touches the empty parent (empty→empty, harmless) and overwrites only `.openapi-generator/FILES` (which phantasos never reads). All emitted imports carry the full dotted prefix. So **N runs into one `project_dir` is the natural mechanism — no post-move, no merge.** `generate.py` needs no change (it already takes a per-call `package`; a dotted value works).

**F2 — Per-sub-package facade works unchanged.** `_discover_resources`' `_IMPORT_RE` (`render.py:15`) swallows any package prefix; facade/resources templates use **relative** imports (`client.py.jinja:12`); `build_wrapper_context`/`introspect` take the package as a parameter. Point them at `prisma_access.objects` and each sub-package gets its own `extras/facade.py` → its own `Client`. No facade-engine change.

**F3 — Shared auth is trivial (pull model).** The token is decoupled from `Configuration` via a `TokenManager`; `SdkConfiguration.access_token` is a read-only property → `self._token_manager.token()`, read fresh per request by `auth_settings()` (`scm_oauth.py.jinja:35-85`, confirmed in built `prisma-browser-sdk/.../api_client.py:643`). Build **one** `TokenManager` at the distribution level and inject it into `SdkConfiguration(token_manager=tm, host=H)` — the constructor already accepts `token_manager=`. One cached token, one refresh, one lock. **Essentially no new auth logic** — only the *vendoring* changes (vendor the shared TokenManager/creds-loader once at the `prisma_access` level, not 12×). *(Rev 5: with the runtime hoisted there is one `Configuration`, so this is **one** `SdkConfiguration` shared by all handles — see D8/§5; rev 3 had one per sub-package.)*

**F4 — One host works for all 12.** The per-domain base-path prefix rides inside each operation's `resource_path` (`/seb-api/v1/...` in built prisma-browser), not the host (`url = host + resource_path`). So one shared `host=` serves every sub-package; each spec's `/config/objects/v1`, `/config/network/v1`, … is already inside its own generated paths. *(P1 caveat: confirm each prisma-access spec encodes its prefix in `paths`; if a spec carries it in `servers`, don't override that package's host — let its own OAG `get_host_settings` default carry it. Either way unblocked.)*

**F5 — One distribution packages the tree.** `scaffold/pyproject.toml.jinja:28` `packages = ["{{ package }}"]` with `package=prisma_access` makes hatchling include the whole `prisma_access/` tree (all sub-packages); `name={{ distribution }}` = `prisma-access-sdk`. Effectively no pyproject change; scaffold runs **once** for the distribution.

**F6 (rev 5) — One shared runtime IS feasible; emit it once.** *(Rev 3 wrongly concluded the opposite — "accept N runtime copies." Re-tracing the built `prisma-browser-sdk` overturned it.)* OAG's `ApiClient.deserialize` resolves models against its own package — `klass = getattr(prisma_browser.models, klass)` (`api_client.py:455`) — and this is the **only** semantic package-binding in the whole runtime. Everything else is package-agnostic: `configuration.py` (1 ref, a logger name), `rest.py` (1, an exceptions import path), `exceptions.py`/`api_response.py` (0). Models have **zero** runtime imports (grep-verified) — the 642-file models tree per spec stays federated and untouched. `api/*.py` take `api_client` by injection (`def __init__(self, api_client=None)`) and import the runtime via exactly one line (`from <pkg>.api_client import ApiClient, RequestSerialized`); the facade already constructs one `ApiClient` and shares it across a package's resources. So the runtime is emitted **once** under `prisma_access._runtime`, line 455 is abstracted to `getattr(self.models, klass)` (a per-handle attribute), each `api/*.py`'s one runtime-import line is repointed to `_runtime`, and the composer builds one `Configuration` + one `RESTClientObject` (one pool) + N thin `ApiClient` handles, each tagged `handle.models = prisma_access.<slug>.models`. This kills both the ~25k-LOC duplication and the 12 pools; the cost is a **bounded, mechanical generation-time import-rewrite pass** (§8). Collision-free: each handle resolves only its own sub-package's response models, so bare class-name strings in `_response_types_map` need no qualification. (See D8, §5, §8.)

**Overall verdict: FEASIBLE.** OAG is not the obstacle. The work is the `productconfig` rework + the build loop + a small composer template + two surgical bugs.

---

## 2. Investigation facts (unchanged, still verified)

12 specs, **784 ops, 354 paths, 283 schemas**, ~80k lines. OAS 3.0.0 ×10 / 3.0.3 (posture) / 3.1.0 (network-services) — each generated in isolation, so versions never collide (network-services builds alone as 3.1 with skip-validate; `nullable` preserved everywhere). Auth bearer in 11/12 (scheme names `scmToken`/`scmOAuth` ×9, `bearerAuth` ztna, `JWT` incidents); **posture declares none** — a non-event under rev-4 transport-level auth (the bearer is attached regardless of any spec's `security`). `ExternalTags` top-level key in incidents/posture/ztna. Region/tenant headers: incidents **requires** `X-PANW-Region`; ztna optional `x-panw-region` (44/61); `prisma-tenant` optional. Classification per spec: ~77% direct CRUD-verb (zero PATCH ops; 146 PUT updates via PUT→replace fallback, 142 anchor / 3 anchorless) + ~5% need declared anchoring; ztna's 61 dotted ids are the outlier. oneOf per spec (network-services 139, undiscriminated — construction-ergonomics ceiling stands per-package).

---

## 3. Locked decisions (rev 3)

| # | Decision | Notes |
|---|---|---|
| D1 | **Consistent surface, complete payload** | Surface = one distribution + one composing client + one credential + uniform per-sub-package shape; payload = each spec faithful in its own namespace. |
| **D2** | **Federated sub-packages** — per-spec OAG run → `prisma_access.<spec>` sub-package; composed under one distribution `prisma-access-sdk`; no merge. | Replaces rev-2 merge. Proven feasible (F1). |
| D2.0 | **Precursor: validation fix** — strip `ExternalTags` (preprocess) + per-product `GeneratorConfig.skip_validate_spec` (network-services false positive). | No version unification, no merge target (dissolved). |
| **D3** | **Navigability by package** — each spec its own namespace; cross-spec same-named schemas coexist (no dedupe). Sub-package slug = spec filename, `-`→`_` (`security-services`→`security_services`). | The rev-2 collision machinery is gone. |
| **D4** | **One shared `TokenManager`, one host, one `Configuration`** (pull model, F3/F4; one `Configuration` per D8/rev 5). **Bearer injected at the transport layer** (vendored `_BearerApiClient`), spec-agnostic — no `inject_security`, no scheme-name matching. Region/tenant = decoupled `default_headers` config w/ per-call override. | No prefix folding; no OR-merge; no spec security mutation. |
| **D5** | **Per-spec sub-package facade + a thin top-level composing `Client`** (`client.objects.<obj>.<verb>()`, `client.posture.…`), all sharing the one TokenManager. Classification/anchoring per sub-package. | Composer is the consistency layer (north star); MVP could ship sub-package facades first (P-phasing). |
| D6 | **`sdk.yml` `subpackages: [...]`**; `package=prisma_access` (namespace root), one `distribution`/`project`. Auto the mechanical, declare the semantic (ztna `normalize_operation_ids`; posture needs nothing — bearer is transport-level, rev 4). | Largest code change (F-verdict). |
| D7 | **Full design, phased de-risked build** | P1 first-light proves OAG nesting + per-spec base-path + one-token-shared on 2-3 specs before the full loop. |
| **D8** | **Single shared runtime (rev 5, overturns F6)** — emit the OAG runtime **once** under `prisma_access._runtime`; abstract the lone package-bound line (`getattr(self.models, klass)`); composer builds **one** `Configuration` + **one** connection pool + **N thin `ApiClient` handles** each tagged `.models = <slug>.models`. Models tree stays federated. | One client, one pool. Cost = a bounded generation-time import-rewrite pass (§8). Collision-free per-handle. |
| **D9** | **Federated docs site (rev 6)** — **one** distribution MkDocs site; `gen_ref_pages` loops the sub-packages so the API Reference covers **all 12** (grouped by sub-package); CRUD/auth/pagination guides teach **one** representative showcase (`client.objects.address`). Runtime SDK needs no extra wiring. | Docs generator is package-singular today (`docs.py:202-206`, `gen_ref_pages.py.jinja`); make it sub-package-aware (§6.1/§8). Option-B per-sub-package guides deferred (anti-scope). |
| **D10** | **CLI forward-compat affordance (rev 7)** — composer exposes a **`_SUBPACKAGES` registry** (slug → sub-package facade `Client`), mirroring `_WRAPPERS`/`_RESOURCES`, so docs + a future CLI enumerate sub-packages by introspecting the **built artifact**. Federation preserves the CLI's per-package introspection contract intact. | CLI itself **out of scope** this round (§6.2). Non-binding lean: verb-first `[verb, sub-package, object]`. The nestable `typer_path` + per-sub `_WRAPPERS` support both tree shapes. |

---

## 4. Architecture — federated build pipeline

Load N sub-package specs → **per (spec, sub-package) loop**: normalize → OAG generate (`--package-name prisma_access.<sub>`) → patches → vendor facade → `_about`. Then **once** for the distribution: **hoist the runtime to `_runtime` + repoint api imports** (D8), vendor the shared auth/TokenManager, render the composing `Client`, render the scaffold, smoke each sub-package.

```
products/prisma-access/sdk.yml  (package: prisma_access; subpackages: [{slug, spec, …}, ×12])
        │
        ▼  for each sub-package (objects, posture, …):
   ┌─ per-spec NORMALIZE (existing preprocess, per-spec) ─────────────────────┐
   │  • generic clean + strip ExternalTags                                    │
   │  • declared semantics: normalize_operation_ids (ztna)                    │
   │  • NO version change, NO merge                                           │
   └──────────────────────────────────────────────────────────────────────────┘
        │
   generate  --package-name prisma_access.<slug>  (skip_validate_spec per-product)  → project_dir/prisma_access/<slug>/
   patches.apply_generic_patches(<slug> pkg_dir)                 (per sub-package)
   render.vendor(<slug> pkg_dir, …, distribution_root=project_dir)  → <slug>/extras/facade.py   (per sub-package)
   _about.py                                                     (per sub-package)
        │
        ▼  once for the distribution:
   HOIST RUNTIME (D8):  move one sub-package's {api_client,configuration,rest,exceptions,api_response}.py
        → prisma_access/_runtime/  (rewrite intra-runtime imports <slug>→_runtime;
          abstract line 455: import prisma_access.<slug>.models / getattr(...models,klass)  →  getattr(self.models, klass);
          add models= param to ApiClient.__init__)
     delete the 5 runtime files from every sub-package
     repoint each prisma_access/<slug>/api/*.py runtime import  →  prisma_access._runtime  (models imports stay federated)
   vendor shared TokenManager + _BearerApiClient(_runtime.ApiClient) + credential loader at  prisma_access/_auth.py
   render composer  prisma_access/__init__.py  (Client → .objects/.posture/…; ONE Configuration + ONE pool + N tagged handles)   ← written LAST
   scaffold.render_scaffold(...)  (one pyproject, distribution = prisma-access-sdk)
   smoke each sub-package (walk prisma_access/<slug>/api/*_api.py)
```

The composing `Client` builds the one `TokenManager`, **one** `SdkConfiguration(token_manager=tm, host=H)` and **one** shared `RESTClientObject` (one connection pool), then for each sub-package a thin `_BearerApiClient(cfg, models=prisma_access.<slug>.models)` whose `rest_client` is the shared pool, injected into that sub-package's facade `Client(api_client=…)`. `client.objects` *is* the objects sub-package facade (with `.address`, etc.), so `client.objects.address.create(...)` — one runtime, one token, one pool underneath.

---

## 5. Transport / auth (D4)

- **One credential, one TokenManager, one Configuration (rev 5):** vendored once at `prisma_access/_auth.py`. With the runtime hoisted to `prisma_access._runtime` (D8) there is now **one** OAG `Configuration` class, so the `SdkConfiguration` subclass is defined **once** (`SdkConfiguration(prisma_access._runtime.configuration.Configuration)`) and the composer instantiates it **once** — one token, one refresh, shared lock, shared `RESTClientObject`/connection pool. (Pre-rev-5 this was N `SdkConfiguration`s, one per sub-package's own OAG `Configuration`.)
- **Transport-level bearer (rev 4, on the shared runtime):** the vendored `_BearerApiClient(prisma_access._runtime.ApiClient)` overrides `update_params_for_auth` to unconditionally set `Authorization: Bearer <self.configuration.access_token>` (the pull-model property — still read fresh per request). The composer builds N thin `_BearerApiClient` handles (one per sub-package, each tagged `.models`), all sharing the one `Configuration` + pool. This sidesteps OAG's spec-driven path (`if not auth_settings: return`, `api_client.py:630`) entirely:
  - **posture** (declares no scheme, so its ops emit `_auth_settings = []`) sends the token with **no spec mutation** — `inject_security` is gone.
  - the 11 divergent scheme names (`scmToken`/`scmOAuth`/`bearerAuth`/`JWT`) no longer need to match per sub-package; the hook ignores `_auth_settings`.
  - **Safe (maintainer-confirmed):** every endpoint across all 12 specs sits behind auth, and the token endpoint is hit directly by `TokenManager._fetch` (urllib3, not via `ApiClient`), so attaching the bearer unconditionally is a non-issue.
- **One host** (F4): set once on the composer; rides with each sub-package. P1 confirms paths-vs-servers per spec.
- **Region/tenant headers — decoupled `default_headers` config:** declared in `sdk.yml` (§7), not derived from any spec's `security`/params; required-ness carried declaratively (`required_for: [incidents]` → fail-loud if unset); per-call override. One default-header layer in the generated config.

---

## 6. Surface — per-sub-package facade + composer (D5)

- Each sub-package gets its own `extras/facade.py` `Client` and typed resource wrappers (F2), classified/anchored **within that package** — so the rev-2 cross-spec object-collision question is moot by construction (different packages). Per-package classification: ~77% direct + PUT→replace fallback + declared anchoring for the 3 anchorless PUTs and the non-CRUD ops; ztna's 61 dotted ids handled by its `normalize_operation_ids` rule (strip `.v2`, dots→`_`, unify separators) + `operations:` for residue.
- **Top-level composing `Client`** (new template `components/facade/composer.py.jinja`, rendered once, written last so it overwrites OAG's empty parent `__init__`): exposes `.objects`/`.posture`/… each delegating to the sub-package facade, all sharing the one TokenManager. This is what makes 12 packages feel like one SDK. Users may also import a sub-package directly (`from prisma_access.objects.extras.facade import Client`).
- **`_SUBPACKAGES` registry (rev 7, D10):** the composer module also exports `_SUBPACKAGES` (slug → sub-package facade `Client`), mirroring the per-facade `_WRAPPERS`/`_RESOURCES` registries. This is the **enumeration seam** the docs `gen_ref_pages` (§6.1) and a future CLI (§6.2) introspect to walk the sub-packages from the **built artifact** — not by re-reading `sdk.yml`. One dict in the composer template.
- Verb-vocabulary extension (Load/Push/Move/Import/Export/Save/Publish/Convert/Validate/Batch/Start/Stop/Download/Clone/Generate/Compare/Diff/Search/Initiate) is reusable and improves method naming, but does **not** anchor — non-CRUD ops still need an object (sibling CRUD object on the same api class, or `operations:` entry).

### 6.1 Documentation site — federated (D9, rev 6)

The opt-in SDK docs site (`sdk.yml` `docs:`) is **one MkDocs site for the whole distribution**, rendered once in the post-loop distribution step (alongside the composer/scaffold). The single-spec docs machinery is package-singular and must become sub-package-aware at three points:

- **Reference pages — loop the sub-packages.** `gen_ref_pages.py.jinja` today reads one `{package}.extras.facade._WRAPPERS` + walks one `{package}/models` tree. It instead iterates **`prisma_access._SUBPACKAGES`** (the composer registry, D10): for each `<slug>`, import `prisma_access.<slug>.extras.facade._WRAPPERS` (one page per `<Object>Resource`) and walk `prisma_access.<slug>/models` (one page per model, oneOf variants linked) — emitting pages under `reference/<slug>/…`. The literate-nav `SUMMARY.md` then auto-groups the API Reference by sub-package. This is the bulk of the docs value (every wrapper + model across all 12) and comes essentially for free once the loop exists.
- **Showcase context — target the showcase's sub-package.** `build_docs_context` (`docs.py:202-206`) runs `cli_operations`/facade-validate/`models` import against `prisma_access.<showcase_sub>` (not the root), and the showcase attr becomes `<slug>.<object>` so the guides render `client.objects.address.create(...)`. One representative showcase for the whole site (D9; per-sub-package guides are anti-scope).
- **Config + nav — one showcase, one guide set.** `DocsConfig.showcase_resource` is qualified `objects.address` (or a `showcase_subpackage: objects` + `showcase_resource: address` pair). `mkdocs.yml.jinja` nav is structurally unchanged — one CRUD/auth/pagination guide set; only the API-Reference subtree grows (auto, via literate-nav).
- **Validation:** the `sdk-docs` nox session builds the site with `mkdocs build --strict` — a sub-package that fails to contribute reference pages (e.g. the loop silently covering only the empty root) fails the build, not ships empty.

### 6.2 CLI forward-compatibility (D10, rev 7 — CLI itself out of scope)

The CLI is **not built this round**, but the SDK is its substrate, so the federated architecture is checked against the CLI generator's contract to avoid a later corner:

- **The contract is preserved intact.** `phantasos cli build` introspects the **built SDK**: `introspect`/`cli_operations(package, sdk_path)` read `extras.facade._RESOURCES`/`_WRAPPERS`; `build_model_registry` the schemas; the emitted Typer tree is verb-first with a **nestable `typer_path` list** (`app.py.jinja:82-91`). Each federated sub-package keeps its own `_WRAPPERS`/`_RESOURCES` (F2), so `cli_operations("prisma_access.objects", out)` works **per sub-package, unchanged** — and `client.objects.address.create()` maps 1:1 onto a CLI command path. Federation requires **no CLI-engine change to be feasible.**
- **Two deferred CLI-side tasks** (named, not done): (1) the host `_build_ir_or_exit` is single-package-keyed (`cli.py:42`, `cli_operations(loaded.config.package, …)`) — for `prisma_access` it must **loop the sub-packages** via `_SUBPACKAGES` (the same shape as the docs fix) and compose; (2) the command tree gains **one level** for the sub-package — additive, since `typer_path` already nests.
- **Recorded non-binding lean:** verb-first `prisma-access <verb> <sub-package> <object>` (`typer_path = [verb, subpackage, object]`), extending today's `_VERBS` grouping. Resource-first (`<sub-package> <object> <verb>`, mirroring the SDK call) is equally supported; the real decision lands in the CLI spec.
- **Cross-sub-package object-name collisions** (e.g. two sub-packages each exposing `address`) are resolved by the sub-package command level — the same way the SDK resolves them by namespace. No global object-name uniqueness is required; the per-sub `_WRAPPERS` already scope objects within a sub-package.
- **Affordance only:** the sole SDK-side concession to the CLI is the `_SUBPACKAGES` registry (D10/§6) — already needed by the docs (§6.1). Nothing else about the CLI is designed or built here.

---

## 7. Config surface — `sdk.yml` (D6)

```yaml
package: prisma_access                      # namespace root (sub-packages hang off this)
distribution: prisma-access-sdk
output: ../../../prisma-access-sdk
base_url: https://<gateway-host>            # one host (F4); P1-verified
auth: { type: scm_oauth, ... }              # one credential → one shared TokenManager
generator: { skip_validate_spec: true }     # per-product (network-services false positive)
default_headers:
  x_panw_region: { env: PANW_REGION, required_for: [incidents] }
  prisma_tenant: { env: PRISMA_TENANT, required: false }
subpackages:
  - { slug: objects,            spec: openapi/objects.yaml }
  - { slug: network_services,   spec: openapi/network-services.yaml }   # 3.1.0, generated alone (lossless)
  - { slug: posture,            spec: openapi/posture.yaml }   # no scheme in spec; bearer attached at transport (rev 4)
  - { slug: ztna_connector,     spec: openapi/ztna-connector.yaml,
      normalize_operation_ids: { strip_suffix: .v2, dots_to_underscore: true, unify_separator: _ } }
  # … 8 more, mostly just {slug, spec}
docs:                                       # opt-in; one site for the distribution (D9/§6.1)
  showcase_subpackage: objects              # which sub-package the guides showcase
  showcase_resource: address                # → guides render client.objects.address.<verb>()
  site_name: Prisma Access SDK
project: { author: ..., repo_url: ... }
```

`ProductConfig`'s singular `package`/`spec` gains a `subpackages` list; `package` becomes the namespace root, each `SubPackage` carries `{slug, spec, transforms?, operations?, normalize_operation_ids?}`. `load_product` builds a per-sub context inside the loop plus the top-level distribution context. A `model_validator` keeps the legacy single-spec `spec:`/`package:` form working for the other products (under `extra="forbid"`).

---

## 8. Code-change map (file:line, from feasibility)

| Area | File | Change |
|---|---|---|
| **Config (largest)** | `productconfig.py:105-127` | singular `package`/`spec` → `package` (root) + `subpackages: list[SubPackage]`; one `distribution`/`output`/`project`. `model_validator` for legacy single-spec. |
| Per-sub context | `productconfig.py:238-292` | `context["package"]` (singular) → top-level value + per-sub context in the loop. |
| Build loop | `build.py:54-76,106` | wrap generate+patches+vendor+`_about` in a per-sub loop; scaffold + composer once. |
| **Bug: dotted path** | `build.py:63` | `pkg_dir = project_dir / cfg.package` → `project_dir / Path(*sub.package.split("."))` (else a literal `prisma_access.objects` dir). |
| **Bug: introspect root** | `render.py:186` | `introspect(pkg, pkg_dir.parent)` → pass the **distribution root** (`project_dir`), not `pkg_dir.parent` (nested import needs it on `sys.path`). |
| Validation | `generate.py:64-94` + `GeneratorConfig` (`productconfig.py:97-103`) | add `skip_validate_spec` flag, emit `--skip-validate-spec` only when set (per-product, not blanket). `write_openapi_generator_ignore(project_dir)` once before the loop. |
| Normalize | `preprocess.py` | add `strip_external_tags`; per-spec `normalize_operation_ids` (ztna). **No `inject_security`** (auth moved to transport, rev 4). |
| **Runtime hoist (rev 5, D8)** | new `runtime.py` build step (post-loop) | move one sub-package's `{api_client,configuration,rest,exceptions,api_response}.py` → `prisma_access/_runtime/`; rewrite their intra-runtime imports `prisma_access.<slug>.X` → `prisma_access._runtime.X`; **delete** those 5 files from every sub-package. Bounded, mechanical, generation-time. |
| **Abstract line 455 (rev 5)** | `_runtime/api_client.py` (patch) | drop module-level `import prisma_access.<slug>.models`; `klass = getattr(prisma_access.<slug>.models, klass)` → `getattr(self.models, klass)`; add `models=None` param to `__init__` (`self.models = models`). The lone package-bound line, now per-handle. |
| **Repoint api imports (rev 5)** | `prisma_access/<slug>/api/*.py` (per file) | rewrite the one runtime-import line `from prisma_access.<slug>.api_client import ApiClient, RequestSerialized` (and any `api_response`/`rest`/`exceptions` runtime imports) → `prisma_access._runtime.…`. **Models imports stay federated** (request construction). |
| Shared auth | `render.py:90-91`, `components/auth/scm_oauth.py.jinja` | vendor `TokenManager`/creds-loader **+ `_BearerApiClient(prisma_access._runtime.ApiClient)`** **once** at `prisma_access/_auth.py`; `SdkConfiguration` subclasses the **one** `_runtime` `Configuration`; the composer (not a per-sub factory) builds the N tagged handles. |
| Composer | new `components/facade/composer.py.jinja` + a `build.py` step | render `prisma_access/__init__.py` `Client`: one `TokenManager`, **one** `SdkConfiguration`, **one** `RESTClientObject`/pool, N thin `_BearerApiClient` handles (each `.models = <slug>.models`, `.rest_client = shared pool`) injected into each sub-package facade `Client(api_client=…)`; exposes `.objects`/…; **also export `_SUBPACKAGES`** (slug → sub-package facade `Client`, rev 7/D10) for docs+CLI introspection; **write last**. |
| Smoke | `smoke.py:33-41,116` | `_count_operations`/import-walk per sub-package (parent `prisma_access` has no `api/`). |
| Provenance | `build.py:10-15,106-113` | `_about.py` per sub-package (or one distribution manifest); **fix hardcoded `phantasos_version="0.1.0"`** → `importlib.metadata.version("phantasos")` (architecture-review Appendix A). |
| pyproject | `scaffold/pyproject.toml.jinja:28` | `packages=["{{ package }}"]` with `package=prisma_access` (one line; tree auto-included). |
| **Docs reference (rev 6, D9)** | `scaffold/docs/scripts/gen_ref_pages.py.jinja` | loop **`prisma_access._SUBPACKAGES`** (rev 7/D10) instead of one `PACKAGE`: per `<slug>`, walk `prisma_access.<slug>.extras.facade._WRAPPERS` + `prisma_access.<slug>/models`, emit pages under `reference/<slug>/…`. literate-nav `SUMMARY.md` auto-groups by sub-package. |
| **Docs showcase (rev 6, D9)** | `generator/sdk/docs.py:202-206` | target the showcase **sub-package**: `cli_operations`/facade-validate/`models` import against `prisma_access.<showcase_sub>`; showcase attr → `<slug>.<object>` so guides render `client.objects.address.…`. Site renders **once** for the distribution. |
| **Docs config (rev 6, D9)** | `productconfig.py:64-70` (`DocsConfig`) | add `showcase_subpackage` (qualifies `showcase_resource`); `site_name` defaults to the distribution. `mkdocs.yml.jinja` nav unchanged (one guide set); only the `reference/` subtree grows. |

---

## 9. Phased plan & definition of done (D7)

- **P0 — Foundations.** `subpackages` config model + legacy alias; per-product `skip_validate_spec`; `ExternalTags` strip; the two surgical bugs (`build.py:63`, `render.py:186`). *Verify:* config loads all 12 sub-package entries; existing single-spec products still build unchanged.
- **P1 — First light (de-risk, proves the new mechanism).** Generate 2-3 sub-packages standalone via the loop — **objects** (clean), **network_services** (3.1), **ztna_connector** (outlier) — then run the **runtime hoist** (D8) over them. *Verify:* OAG dotted-name nesting + empty-parent coexistence on a real build; each sub-package imports + smoke-counts; **the hoisted `prisma_access._runtime` + abstracted `getattr(self.models, klass)` round-trips a real response** in ≥2 sub-packages (proves the per-handle `.models` tag deserializes the right namespace — the single rev-5 risk); **one shared `RESTClientObject`/pool** serves multiple handles; **per-spec base-path correct** (paths-vs-servers, F4 caveat) via a live call; one shared `TokenManager` token authenticates across ≥2 sub-packages — **and the transport-level bearer works across divergent scheme names** (objects `scmToken` vs ztna `bearerAuth`), confirming the hook ignores per-op `_auth_settings`.
- **P2 — Full federation.** All 12 sub-packages through the loop; hoist the runtime once; vendor the shared `TokenManager` once; render the composing `Client`; one distribution scaffold. *Verify:* `import prisma_access; Client.from_env()` exposes all sub-packages over **one `Configuration` + one pool + N tagged handles**; one token shared; every sub-package deserializes its own models (no cross-namespace bleed); **posture (no spec scheme) authenticates via the transport-level bearer**; composer overwrites the empty parent `__init__` cleanly.
- **P3 — Surface polish.** Per-sub-package facade classification/anchoring (verb-vocab extension + ztna normalize + `operations:` for the 3 anchorless PUTs + non-CRUD); region/tenant default headers. *Verify:* objects/verbs exposed per package; non-CRUD reachable + anchored; incidents region required-validation fires.
- **P4 — Smoke + live + docs.** Smoke per sub-package; live CRUD where creds exist; **federated docs site** (D9) — `gen_ref_pages` loops the sub-packages, `mkdocs build --strict` via the `sdk-docs` session. *Verify:* all sub-packages import clean; live CRUD passes where creds available; the site builds strict with the API Reference covering **all 12** sub-packages (grouped) + the `client.objects.address` showcase guides.

**Definition of done:** `prisma-access-sdk` builds all 12 sub-packages under `prisma_access`, `import prisma_access` + composing `Client.from_env()` works with **one shared token**, each sub-package smoke-imports clean, posture authenticates, **live CRUD passes where creds exist**, and the **opt-in docs site builds `--strict`** with reference across all sub-packages. CLI out of scope.

---

## 10. Risks (rev 3)

1. **Build/vendor pipeline rework** (the real work, not the tooling) — the `productconfig` singular→list change + the per-sub loop + vendor-once-shared-auth. Largest surface; well-localized (§8).
2. **Per-spec base-path encoding** (paths vs servers) must be consistent/known across all 12 so one host (or per-package default) routes correctly — P1 live check (F4 caveat). The one true silent-404 risk.
3. **Composer parent `__init__` write order** — OAG re-touches the empty parent on each run; the composer must be rendered **last**. (Proven harmless if ordered correctly.)
4. **Runtime-hoist correctness (rev 5, D8)** — the shared `_runtime` replaces rev-3's accepted duplication. The risk shifts from *bloat* to *the rewrite pass being complete*: every `api/*.py` runtime import must repoint to `_runtime`, and every handle must carry the right `.models` tag, or deserialize resolves the wrong namespace (or `None.models`). Mitigated by P1's real-response round-trip across ≥2 sub-packages + per-package smoke; the rewrite is mechanical and bounded (one import line per api file, one abstracted line in api_client). Fail-loud if a handle's `.models` is unset.
5. **oneOf construction ergonomics** (per package, network-services) — patches fix serialization, not construction; standing ceiling.
6. **Provenance** across 12 sub-packages — `_about.py` per package or one manifest.
7. **Docs reference completeness (rev 6, D9)** — the federated `gen_ref_pages` must loop **all** sub-packages, or the API Reference silently covers only some (or, against the empty root, none). Mitigated by `mkdocs build --strict` in the `sdk-docs` session (empty/missing reference fails the build) + a page-count assertion (per sub-package contributes ≥1 reference page).

## 11. Anti-scope

- **No CLI** (keep facades introspectable, build no CLI). The **only** CLI concession is the `_SUBPACKAGES` registry affordance (rev 7, D10/§6.2) — already needed by the docs; no CLI command tree, host-loop, or `cli.yml` work this round. The verb-first command-tree lean is recorded, not implemented.
- **One docs site, one showcase guide (rev 6, D9)** — the opt-in MkDocs site IS in scope (reference loops all 12 sub-packages), but the CRUD/auth/pagination **guides** teach one representative showcase (`client.objects.address`); **no per-sub-package guide proliferation** (the Option-B fork) and no per-sub-package mini-sites this round.
- **No spec merge / no merged package** (the whole point of the pivot).
- **A single shared runtime IS in scope (rev 5, D8)** — one `prisma_access._runtime`, one `Configuration`, one connection pool, N thin `.models`-tagged `ApiClient` handles. (This reverses rev 3's anti-scope exclusion; F6's "package-bound deserialize blocks sharing" was overstated — it's one abstractable line.) Still out of scope: any *deeper* runtime fusion (e.g. literally one `ApiClient` object via dotted-qualified `_response_types_map` + importlib resolution) — the per-handle `.models` tag is collision-free and simpler.
- **No version unification / 3.1→3.0 conversion** (each spec generated alone).
- **No blanket `--skip-validate-spec`** (per-product only).
- **The transport-level bearer (`_BearerApiClient`) IS the one auth strategy** (rev 4) — no per-spec `inject_security`, no scheme-name matching; the one shared SCM-OAuth `TokenManager` satisfies all 12; verify in P1.
- **No frozen-oracle edits**; follow the branch/release workflow (feature → develop, squash, `## [Unreleased]`).
