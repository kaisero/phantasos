# Spec: multispec (federated) CLI generation — prisma-access-cli

- **Status:** Design spec, **rev 2** — grilled (11 decisions), then two expert reviews (python-pro + CLI-UX). Rev 2 folds in the review corrections: the false "only `Command.subpackage` changes / `typer_path` already nests / byte-identical" claims are fixed, a **runtime-federation** section + **model-registry namespacing** are added, the compat goal is restated as **behavioral**, and D6's blast radius is scoped. D1 (mandatory verb→sub→object) is unchanged per maintainer. No code yet.
- **Branch:** `feature/prisma-access-cli` (off `develop`, which carries the federated SDK squash `c505977`).
- **Scope:** Add **multispec/federated support to the CLI generator**, exercised by **prisma-access** (12 SCM specs → one `prisma-access-cli`). Single-spec CLI generation (prisma-browser, posture) must stay **behaviorally identical**. A small enabling change to the **SDK composer** (lazy handles, D6) rides this branch.
- **North star:** the federated CLI feels like **one consistent tool** over all 12 sub-packages — uniform verb-first shape, one credential/config/environment, complete payload — extending the existing single-spec CLI conventions, not inventing new ones.

---

## Business intent — validate before any code

**Who this is for.** A Prisma Access operator who today hand-writes `curl`s against 12 SCM APIs or scripts the SDK. The SDK gives `client.objects.address.create(...)`; this gives `prisma-access set objects address …` — the same surface, with config, named environments, tables, history, and the SCM connection (region/tenant) handled for them.

**What we want.** `phantasos cli build prisma-access` produces **one** Typer CLI exposing all 192 objects across 12 sub-packages under a verb-first tree, with region/tenant as first-class config — the generator change **generic** (any future federated SDK gets a CLI the same way, by introspecting the built artifact).

**Why it matters.** The SDK was explicitly designed for this (D10/rev-7 of the SDK spec: composer exposes `_SUBPACKAGES`, each sub keeps its own `_WRAPPERS`). The deferred work is "loop the sub-packages and add a command level" — but the reviews show the runtime/app emission ripple is larger than that phrase implies (see Architecture).

**Feasibility (measured against the real built SDK).**
- **12 sub-packages, 192 objects, ZERO cross-sub OBJECT-name collisions.** (Note: this is **object** names only. **Model class names DO collide** — 28 across subs, incl. `Tcp`/`Udp`/`ErrorResponse`/`GenericError`. See B3 / model-registry namespacing.)
- **Wrapper-rebased classification is clean per sub** (real SDK, no `cli.yml`): objects 75 commands / **0 unmapped**; network_services 189 / 1; only genuine non-CRUD actions are "unmapped" (→ `request:`).
- `cli_operations("prisma_access.objects", sdk_path)` works per sub unchanged; `_SUBPACKAGES` enumerates the subs from the artifact.

**What this is NOT.** Not a re-classification of SCM operationIds (the CLI consumes the wrapper surface). Not per-sub-package CLIs (one distribution → one CLI). Not docs (P2, opt-in, deferred).

---

## Decisions (grilled + review-adjusted)

| # | Decision | Choice | Notes (rev 2) |
|---|---|---|---|
| **D1** | **Command tree** | **verb-first 3-level**: `prisma-access <verb> <sub-package> <object>` | Sub-package **mandatory** in invocation (maintainer call; auto-resolve considered & declined). Maps 1:1 to `client.<sub>.<object>.<verb>()`. |
| **D2** | **`cli.yml` shape** | **one file, per-sub sections** (`subpackages:` map) | Each sub's section resolves to a normal `CliConfig`-shaped delta fed to that sub's `build_cli_ir` (S3 — no parallel config model). |
| **D3** | **region/tenant (`default_headers`)** | **first-class connection fields** — generalize `credential_fields` | Validated solid: `HeaderSpec` already on `ProductConfig`; `_enrich_ir` is the seam; `CredentialField` is the template. Command-aware pre-flight + env-export seam — see Connection fields. Drop the redundant config-default region (per-environment only). |
| **D4** | **non-CRUD ops** | **explicit `cli.yml request:`** | Mitigation added: a `sdk.yml`-bound non-CRUD op missing its `cli.yml request:` twin is silently **omitted** today (stderr note, not a failure). For federated builds, **fail loud** on an unmapped non-CRUD op (see C2). |
| **D5** | **Phasing** | **thin-slice P0 → enroll all (P1) → opt-in docs (P2)** | P0 model-collision coverage added via the fixture (B3). |
| **D6** | **Client construction** | **lazy SDK handles** | Re-scoped: not "small" — touches `composer.py.jinja` + reworks SDK unit tests (`test_sdk_build.py`, `test_render.py`) + the retry-on-first-sub side-effect. **Docs/smoke-safe** (confirmed). |
| **D7** | **P0 content** | **objects + incidents** | Covers merge, `Command.subpackage`, **len-3 nesting** (`request incidents incident search`), required-header pre-flight, lazy `incidents`, non-CRUD `request:`. Does NOT cover model-collision (disjoint) → fixture canary; ztna host-override deferred to P1. |
| **D8** | **Offline test vehicle** | **new federated `fedsdk` fixture** | `_SUBPACKAGES = {alpha, beta}`; beta = non-CRUD action + REQUIRED header **+ a model-name collision with alpha** (to pin the registry namespacing, B3). |
| **D9** | **Discoverability** | **completion + did-you-mean + a `which` locator** | Locator renamed `find`→**`which`** (alias `where`/`find`) — `find` collides with the real server-side `search` action. `which`/object-leaf also answers "what can I do with X?" (all verbs incl. `request`). |
| **D10** | **`cli discover`** | **per-sub tables + one federated stub** | Unchanged. |
| **D11** | **`request` depth** | **`request <sub> <object> <action>`** | Unchanged (4 visible levels for the rarest commands); app loop is generalized to N-level (B2/S2). |

---

## Architecture

The CLI build is three stages (introspect → classify → render). Federation threads a **sub-package dimension** through all three **and** through the emitted runtime. Host commands `cli_build`/`cli_discover` (`phantasos/cli.py`) gain the loop.

### 1. Introspect + classify — loop the subs, merge into one IR

`cli_build`/`cli_discover` import the built SDK and read `_SUBPACKAGES` from the top-level package (federation **detected from the artifact**, never re-read from `sdk.yml` — D10). For each slug:
- `cli_operations(f"{package}.{slug}", sdk_path)` → per-sub `OperationInventory`.
- `build_model_registry(f"{package}.{slug}", sdk_path, inv)` → per-sub model registry. **(C4: `cli.py:46` today calls `build_model_registry(loaded.config.package, …)`; for federated that's `prisma_access.models`, which does not exist — it must be per-sub.)**
- `build_cli_ir(inv, sub_cfg, models=…)` → per-sub commands, where `sub_cfg` is the `subpackages.<slug>` section as a `CliConfig` (S3).

**Merge** the per-sub command lists into one `CliIR`, stamping `Command.subpackage = slug` (the **snake** slug — C3) on each. The merged IR carries top-level `sdk_package="prisma_access"` and a composer-aware `facade_module`; per-command lookups derive `f"{sdk_package}.{cmd.subpackage}"` (C4). A single-spec package (no `_SUBPACKAGES`) runs the existing single pass with `subpackage=None` — unchanged path.

**Model-registry namespacing (B3 — required).** Model class names collide across subs (`Tcp`, `Udp`, `ErrorResponse`, `GenericError`, …; `registry_from_models` keys by `cls.__name__` and documents this limit at `modelschema.py:138-140`). A flat merged `CliIR.models` would silently overwrite, corrupting the four registry-fed surfaces (`--help` skeleton, docs table, runtime input-error example). **Fix:** make `CliIR.models` a per-sub map (`dict[slug, dict[name, ModelSchema]]`) **or** slug-qualify the keys, and qualify `Flag.model_ref` / `variant_refs` accordingly. Add a **cross-sub OBJECT-uniqueness assertion** at merge (S1), mirroring the slug-uniqueness validator (`productconfig._exactly_one_spec_mode`) — last-writer-wins on a future object collision must fail loud.

### 2. Render — N-level Typer nesting, sub-aware dispatch

**Correction (B2):** `typer_path` does **not** contain the verb (verb is a separate `_REGISTRY` column, `app.py.jinja:37-41,78-83`); today it is `[object]` or `[object, leaf]` and the app loop unpacks **exactly two** elements (`app.py.jinja:84-91`). Federation makes a command's path `[subpackage, object]` or `[subpackage, object, leaf]` (len 3 — e.g. a oneOf variant, or `request <sub> <object> <action>`). So:
- Add `subpackage` to `_REGISTRY`.
- **Generalize the app loop to arbitrary `typer_path` depth** (key `object_apps` by `(verb, *path[:-1])`), not the hard-cased 2-level branch (S2).
- Dispatch becomes two-level: `getattr(getattr(client, cmd.subpackage), cmd.sdk_resource).<clean_method>(...)`.

### 3. Runtime federation (B1 — new, the reviews' biggest miss)

`runtime.py.jinja` resolves **five** things off a single `sdk_package`/`facade_module`, all of which live **per-sub** in the federated SDK. Each must derive `f"{sdk_package}.{cmd.subpackage}"` when `cmd.subpackage` is set, else today's path (single-spec stays behaviorally identical):
- `_models()` → `importlib.import_module(f"{sdk_package}.models")` (`:140-141`) — **no `prisma_access.models`** (models at `prisma_access.<slug>.models`); `_build_body`'s `getattr(_models(), binding.body_model)` (`:321`) would `ModuleNotFoundError`. Must resolve per-sub (and dovetails with the namespaced registry, B3).
- `_facade_from_env` → `facade_module.Client.from_env` (`:45`) — federated entry is `prisma_access.Client(configuration)` (composer), **not** a sub-facade `Client(api_client)`. The runtime constructs the composing `Client` once and navigates `client.<sub>.<object>`.
- `_accepted_params` → `facade_module._WRAPPERS[resource]` (`:161-162`) — top-level has `_SUBPACKAGES`, not `_WRAPPERS`; resolve per-sub.
- `_sdk_exc()` → `f"{sdk_package}.exceptions"` (`:146-150`) — no top-level module; the exceptions live under `_runtime`/per-sub; point it at the real module so SDK errors stay funneled.
- `_dry_run` → `f"{pkg}.api_client"`/`.configuration` + `facade.Client(ApiClient(...))` (`:361-365`) — none at top level and the composer signature differs; rework so dry-run serializes via the sub's wrapper `_serialize` seam.

Plus dispatch (`api = getattr(client, cmd.sdk_resource)`, `:511`) → two-level via `cmd.subpackage`. **The spec owns this as first-class work, not an IR tweak.**

### 4. Connection fields (D3) — generalize the credential path

`render_cli._enrich_ir` (`render_cli.py:312-326`) already enriches the IR with `credential_fields` (from `loaded.auth`) and `error_envelope` (from `loaded.errors`). Add `connection_fields` from `loaded.config.default_headers` (`HeaderSpec`: name, `env`, `required`/`required_for` — already modeled, `productconfig.py:128-139,174`) as a frozen `ConnectionField` descriptor (template: `CredentialField`, `ir.py:22-49`). The emitted `environment`/`config`/`runtime`/pre-flight templates iterate **both** credential and connection fields ("environment fields").
- **Command-aware pre-flight (C3):** move connection pre-flight into `run()` (which has `cmd`, `runtime.py.jinja:453`) — require a connection field only when `cmd.subpackage ∈ field.required_for` (or the header is globally `required`). The snake-slug match is why `Command.subpackage` stores the snake slug.
- **Env-export seam (C3):** the runtime sets `os.environ[field.env] = value` (from `--region` flag > env > active environment > config) **before** constructing the composing `Client`, because the composer reads region/tenant from `os.environ` (`__init__.py:83,114`) and there is **no header kwarg path**. Note: process-global mutation, acceptable for a one-shot CLI.
- **Pre-flight error UX:** exit-2 naming the missing env var, the active environment, *why* it's needed now ("the `incidents` sub-package requires a region"), and a one-line fix (`environment create … --region <r>` / the `--region` example).

### 5. SDK composer — lazy handles (D6)

Change `composer.py.jinja` so each `self.<slug>` builds on first access (cached property / `__getattr__`); the `required_for` env check moves into that lazy build. `client.objects.address` never touches incidents/ztna, so region is only required when those subs are used.
- **Re-scope (C1):** reworks `test_sdk_build.py:282-287` (asserts the raise **at construction** — now at first access), `:313` (per-sub `getattr` access), and `test_render.py:599` (`"self.objects ="` source-assert) + `:646-648` (raise text). The **retry-on-first-sub** side-effect (`composer.py.jinja:53-55`) becomes "first *accessed* facade wires retry" — the refactor must not assume `objects` is accessed first. Add a render/unit-level lazy-behavior assertion (the `fedsdk` fixture does not exercise `composer.py.jinja`).
- **Docs/smoke-safe (confirmed):** `gen_ref_pages` iterates the `_SUBPACKAGES` class registry + per-sub `_WRAPPERS` and never instantiates `Client`; SDK smoke import-walks modules only. Risk is confined to the two SDK unit tests above.

### Discoverability (D9)

Typer completion at verb/sub/object levels (enumerated from the IR). A wrong/missing sub → "did you mean: `<verb> <sub> <object>`" from the IR's global object→sub index (unique object names make it unambiguous). A top-level **`which <object>`** (alias `where`/`find`) prints the object's sub-package **and** its full verb set including `request` actions, giving verb-first the object-centric "what can I do with X?" view it otherwise lacks. Per-object one-line descriptions (reuse the registry `ModelSchema.description`) tame the 50-object `network-services --help`.

---

## `cli.yml` — federated format (D2)

```yaml
# products/prisma-access/cli.yml  (mirrors the federated sdk.yml)
project: { … }
subpackages:
  objects:
    columns: { address: [name, ip-netmask, folder] }
  incidents:
    request:
      incidents_apis.search_incidents: { object: incident, action: search }
  ztna_connector:
    request:
      connector.download_connector_packet_capture_file:
        { object: connector-packet-capture, action: download }
    hide: [ connector.stop_connector_packet_capture ]
```

Each sub section → a `CliConfig` delta for that sub's `build_cli_ir` (S3); today's loud validation of `defaults`/`columns`/`request`/object keys works per-sub unchanged. **Federated builds additionally fail loud** when a `sdk.yml`-bound non-CRUD op has no `cli.yml request:`/`hide:` (C2 — no silent command omission).

---

## Phasing

**P0 — architecture + the novel path on `objects` + `incidents`.**
- The `_SUBPACKAGES` loop + per-sub `build_cli_ir` + `build_model_registry`, merged into one `CliIR` (`Command.subpackage`, namespaced `models`).
- **Runtime federation** (B1): the per-sub resolution of models/facade/exceptions/dry-run/params + two-level dispatch.
- **N-level `app.py` nesting** (B2) — proven by `request incidents incident search` (len-3).
- Connection fields end-to-end (IR enrichment, `environment`/`config`, `--region`/`--tenant`, command-aware pre-flight, env-export); incidents proves required `X-PANW-Region` + the non-CRUD `search`.
- SDK composer **lazy handles** (D6) + the SDK unit-test rework.
- The `fedsdk` fixture (D8) **with an alpha/beta model-name collision** so the registry namespacing (B3) is pinned offline; **build + smoke green** for `prisma-access * {objects,incidents} *` against the real SDK.
- `cli discover` per-sub presentation + federated stub (D10).

**P1 — enroll the remaining 10 subs.** The per-sub `request:`/`columns`/`hide` deltas (≈30 `request:`); the ztna host-override + on-handle header path; a federated oneOf-variant command if one arises; the cross-sub object-uniqueness + unmapped-non-CRUD assertions exercised at full scale; build + smoke + a `live` CRUD round-trip.

**P2 — opt-in federated CLI docs** grouped by sub-package (anti-scope for P0/P1).

---

## Testing

- **Offline / fast (gate):** the `fedsdk` fixture — the generator genuinely introspects a 2-sub fake SDK (`alpha` CRUD, `beta` non-CRUD + required header + a model-name collision with alpha). Behavioral tests through the emitted CLI (`CliRunner`): verb→sub→object dispatch, merged-IR `subpackage`, **namespaced model registry** (collision resolves to the right sub's model), connection-field command-aware pre-flight (exit-2 only when the invoked sub requires the header), `which`/did-you-mean, the federated `cli discover` table + stub, N-level `request` nesting. No introspection-boundary mocking.
- **Slow / smoke (CI):** build the real prisma-access CLI for P0's subs (all 12 in P1) and import-walk it; enroll in `nox.toml [smoke]`. A render/unit assertion pins D6's lazy composer behavior.
- **Live (phase gate):** real CRUD round-trip when credentials + region present (skips otherwise).
- **Backward-compat = BEHAVIORAL (B4).** Single-spec emitted CLIs run identically; their `ir.json` gains a defaulted `"subpackage": null` and `spec.py` gains the `Command.subpackage` field (both *not* byte-identical — `spec.py` is a verbatim copy of `ir.py`, `render_cli.py:490-492`; `ir.json` serializes defaults). Regenerate the affected content assertions in `tests/test_cli_ir.py` / `tests/test_cli_render.py`; pin single-spec **behavior**, not bytes.

---

## Anti-scope

- No re-classification of SCM operationIds (CLI consumes the wrapper surface).
- No per-sub-package CLIs (one distribution → one CLI).
- No federated CLI docs in P0/P1 (P2).
- No divergent-per-sub auth/errors machinery (one `scm_oauth`, generic-fallback errors — validated for prisma-access).
- No change to single-spec CLI **behavior**.

---

## Open items / risks

1. **Runtime federation (B1) is the bulk of the real work** — ~6 `runtime.py.jinja` helpers become sub-aware. P0 must own it (not defer).
2. **Model-registry namespacing (B3)** is an IR-shape change; pinned offline by the `fedsdk` collision canary so it isn't first discovered in P1.
3. **D6 composer change** + its SDK-unit-test rework + the retry-on-first-*accessed*-sub side-effect; docs/smoke confirmed safe.
4. **Compat is behavioral, not byte-identical (B4)** — restated above; update `test_cli_ir`/`test_cli_render` assertions.
5. **D4 silent-omission (C2)** — federated builds fail loud on unmapped non-CRUD.
6. **Component-uniformity** holds for prisma-access (one auth; per-op pagination; generic error fallback) — confirm in P0.

---

## Feasibility appendix (measured)

- `_SUBPACKAGES` = 12 slugs; per-sub `_WRAPPERS` = **192 objects, 0 OBJECT collisions**; **but 28 MODEL-class-name collisions** across subs (B3).
- Wrapper-rebased classification (real SDK, no `cli.yml`): objects 75/0-unmapped, network_services 189/1, ztna_connector 48/8, posture 5/4, incidents 1/1 — unmapped = genuine non-CRUD only.
- `default_headers`: `X-PANW-Region {env: PANW_REGION, required_for: [incidents, ztna_connector]}`, `prisma-tenant {env: PRISMA_TENANT, required: false}`.
- Composer builds all 12 handles **eagerly** and raises on missing `PANW_REGION` for incidents/ztna → motivates D6.
- `runtime.py.jinja` resolves models/facade/exceptions/dry-run/params off a single package (B1) — federation work, not an IR tweak.
- Existing `fakesdk`: hand-written `extras/facade.py` introspected offline → `fedsdk` mirrors it federated (D8).
