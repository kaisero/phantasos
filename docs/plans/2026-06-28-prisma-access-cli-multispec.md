# Implementation plan: multispec (federated) CLI generation — prisma-access-cli

> **For agentic workers:** REQUIRED SUB-SKILL — use `subagent-driven-development` (one fresh implementer per task, two-stage review after each) or `executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Implementers on Opus** (min Sonnet) per maintainer preference. Each task = a failing test → implement → green → commit; the codebase is green (`nox -s gate`) after every task.

- **Spec:** `docs/specs/2026-06-28-prisma-access-cli-multispec-design.md` (**rev 2** is authoritative — it folds in the two expert reviews).
- **Branch:** `feature/prisma-access-cli` (off `develop`, which carries the federated SDK squash `c505977`).
- **Goal (P0):** prove the whole multispec architecture on **two real sub-packages** — `objects` (clean CRUD) and `incidents` (required region + a non-CRUD `search`) — end to end: one `prisma-access-cli` whose `<verb> <sub> <object>` commands dispatch `client.<sub>.<object>.<verb>()`, with region/tenant as connection fields and command-aware pre-flight. Then P1 enrolls the other 10; P2 adds opt-in docs.

## Architecture (what changes, per rev 2)

The CLI build threads a **sub-package dimension** through introspect → classify → render **and** through the emitted **runtime** (the reviews' biggest correction: this is not an IR-only change):
1. `cli_build`/`cli_discover` detect federation from the built artifact (`_SUBPACKAGES`), loop the subs, run the existing `cli_operations`/`build_model_registry`/`build_cli_ir` **per sub**, and **merge** into one `CliIR` (`Command.subpackage` = snake slug; **model registry namespaced per sub**).
2. `app.py.jinja` generalizes from the hard-cased 2-element unpack to **N-level `typer_path` nesting**.
3. `runtime.py.jinja`'s ~6 single-package lookups (models / facade / exceptions / dry-run / accepted-params / dispatch) become **sub-aware** via `f"{sdk_package}.{cmd.subpackage}"`.
4. Connection fields (region/tenant) ride the existing `credential_fields`/`_enrich_ir` path; pre-flight is command-aware; the runtime exports the value to the SDK's env var before constructing the composing `Client`.
5. The SDK composer builds handles **lazily** (D6) so a region is required only when a region-requiring sub is touched.

**Tech stack:** Python 3.11+, pydantic v2, Typer + Rich, jinja2; pytest + nox; ruff + mypy (strict).

## Global constraints

- **Single-spec CLIs stay BEHAVIORALLY identical** (NOT byte-identical — `spec.py` is a verbatim copy of `ir.py`, so adding `Command.subpackage` necessarily changes `spec.py`/`ir.json`; pin behavior, regenerate the affected `tests/test_cli_ir.py` / `tests/test_cli_render.py` content assertions).
- **`Command.subpackage` stores the SNAKE slug** (`required_for` + `getattr(client, slug)` use snake); kebab is display/Typer-only.
- **Do NOT DRY across `generator/sdk` ↔ `generator/cli`** (separation of duty).
- **Do NOT edit frozen oracles** (`.claude/harness.toml` `protected_globs` = `tests/acceptance/**` + `.claude/**`). The CLI/SDK unit tests are NOT frozen — editable.
- **uv/nox env hygiene (this machine):** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/pacli` for `uv run …`; venv-backed sessions (`tests`/`smoke`/`live`) also `NOX_ENVDIR=$HOME/.tmp/pacli-nox`. Do NOT set `TMPDIR`.
- **Phase gate:** `nox -s gate` after every task; `nox -s smoke` (real build) + `nox -s live` (skips without creds) before declaring P0 done. Update `.agents/context/cli-generator.md` + run `nox -s context` (`-- --check` must pass) when the narrative changes.
- **Branch/PR:** all on `feature/prisma-access-cli`; PR `--base develop`; **squash**; **no version bump**; record under `## [Unreleased]`.

---

## P0 — architecture + the novel path (objects + incidents)

### Batch A — foundation & the offline test vehicle

- [ ] **A1 — Add `Command.subpackage` to the IR.** `ir.py`: add `subpackage: str | None = None` to `Command` (additive, default None). Mirror into `spec.py` is automatic (verbatim copy on render). Update the single-spec `ir.json`/`spec.py` content assertions in `tests/test_cli_ir.py` / `tests/test_cli_render.py` to the new shape (the new defaulted `"subpackage": null` field) and assert single-spec **behavior** unchanged. *Test: a single-spec `build_cli_ir` produces `subpackage=None` on every command; serialized IR round-trips.*

- [ ] **A2 — New federated `fedsdk` fixture.** `tests/fixtures/fedsdk/fedsdk/`: a hand-written fake **federated** SDK mirroring `fakesdk` but with `_SUBPACKAGES = {"alpha": …, "beta": …}` on the top-level `__init__`, a **lazy** composing `Client` (cached-property handles; `beta` reads a REQUIRED header env on first access — mirrors the post-D6 composer), and per-sub `alpha/extras/facade.py` (`_WRAPPERS`: `widget` CRUD) + `beta/extras/facade.py` (`_WRAPPERS`: `gadget` CRUD + a non-CRUD `compute` action). **Bake a model-name collision:** `alpha.models.Status` and `beta.models.Status` are distinct classes (pins B3). *Test: `cli_operations("fedsdk.alpha", fixture)` and `("fedsdk.beta", …)` each introspect; `_SUBPACKAGES` enumerates both.*

### Batch B — generator merge (offline, against `fedsdk`)

- [ ] **B1 — Federation-aware host build.** `phantasos/cli.py` `cli_build`/`cli_discover`: detect `getattr(pkg, "_SUBPACKAGES", None)`; when present, loop slugs → per-sub `cli_operations(f"{package}.{slug}", …)`, `build_model_registry(f"{package}.{slug}", …)` (C4 — NOT `build_model_registry(package, …)`, which would hit the non-existent `prisma_access.models`), `build_cli_ir(inv, sub_cfg)` → **merge** command lists into one `CliIR` (top-level `sdk_package=package`, composer-aware `facade_module`), stamping `Command.subpackage=slug`. No `_SUBPACKAGES` → today's single pass (unchanged). Add a **cross-sub object-uniqueness assertion** (S1) — duplicate object across subs fails the build. *Test (fedsdk): merged IR has alpha+beta commands, each with the right `subpackage`; a forced duplicate object raises.*

- [ ] **B2 — Namespace the model registry (B3).** `modelschema.py` / `ir.py`: make `CliIR.models` a per-sub map (`dict[slug, dict[name, ModelSchema]]`) or slug-qualify keys; qualify `Flag.model_ref` / `variant_refs` to carry the slug. The merge stores each sub's registry under its slug. *Test (fedsdk): `alpha`'s `Status` and `beta`'s `Status` both resolve to the correct fields — no overwrite.*

- [ ] **B3 — Federated `cli.yml` format.** `cliconfig.py`: a `subpackages: dict[slug, CliConfig-delta]` section (S3 — each resolves to a normal `CliConfig` fed to that sub's `build_cli_ir`; reuse, don't fork the model). Federated builds **fail loud** when a `sdk.yml`-bound non-CRUD op has no `cli.yml request:`/`hide:` (C2 — no silent command omission). *Test: a fedsdk `cli.yml` with a per-sub `request:`/`columns` applies to the right sub; an unmapped non-CRUD op fails the federated build.*

### Batch C — render & runtime (offline, against `fedsdk`)

- [ ] **C1 — N-level `app.py` nesting (B2/S2).** `app.py.jinja` + `render_cli._command_view`: add `subpackage` to `_REGISTRY`; generalize the app loop to arbitrary `typer_path` depth (key `object_apps` by `(verb, *path[:-1])`), replacing the 2-element unpack. Federated path = `[subpackage, object]` / `[subpackage, object, leaf]`. *Test (rendered): `show alpha widget` and a len-3 `request beta gadget compute` both emit a working Typer path; single-spec emits the 2-level tree unchanged.*

- [ ] **C2 — Runtime federation (B1).** `runtime.py.jinja`: make sub-aware (derive `f"{sdk_package}.{cmd.subpackage}"` when set, else today's path) — `_models()` (per-sub models module; pairs with the namespaced registry), `_facade_from_env` (construct the composing `Client` once, navigate `client.<sub>.<object>`), `_accepted_params` (per-sub `_WRAPPERS`), `_sdk_exc()` (real exceptions module), `_dry_run` (serialize via the sub wrapper's `_serialize` seam), and dispatch `getattr(getattr(client, cmd.subpackage), cmd.sdk_resource)`. *Test (fedsdk emitted CLI, `CliRunner`): `show alpha widget` dispatches; `--dry-run` shows the request; an SDK error is funneled to the diagnostics; single-spec runtime behavior unchanged.*

### Batch D — connection fields (offline, against `fedsdk`)

- [ ] **D1 — `ConnectionField` IR descriptor.** `ir.py`: a frozen `ConnectionField` (name, `env`, `required`, `required_for: list[str]`) — template off `CredentialField`. `render_cli._enrich_ir`: derive `ir.connection_fields` from `loaded.config.default_headers` (`HeaderSpec` already on `ProductConfig`), enriching the `model_copy` BEFORE any render/`ir.json` write (same as `credential_fields`). *Test: a fedsdk product with a `default_headers`-style required header yields `ir.connection_fields`.*

- [ ] **D2 — Emit + layer connection fields.** The `environment`/`config` templates iterate **both** credential and connection fields ("environment fields"): `environment create` prompts region/tenant; `config`/`--region`/`--tenant`; layering `--flag > env > active-env > config` (drop the redundant config-default region — per-environment only). The runtime sets `os.environ[field.env] = value` **before** constructing the `Client` (C3 — the composer reads from env; no header kwarg path). *Test (fedsdk emitted CLI): `--region`/active-env value reaches the SDK; precedence holds.*

- [ ] **D3 — Command-aware pre-flight.** In `run()` (has `cmd`), require a connection field only when `cmd.subpackage ∈ field.required_for` (or globally `required`); clean **exit-2** naming the env var, the **active environment**, *why* ("the `beta` sub-package requires …"), and a one-line fix. *Test (fedsdk): `show beta gadget` with the required header unset → exit-2 with the message; `show alpha widget` with it unset → succeeds (no region needed).*

### Batch E — SDK composer lazy handles (D6)

- [ ] **E1 — Lazy composer handles.** `sdk/components/facade/composer.py.jinja`: build each `self.<slug>` on first access (cached property / `__getattr__`); the `required_for` env check moves into the lazy build; **retry-on-first-*accessed*-sub** (don't assume `objects` is accessed first). Rework the SDK unit tests this changes — `tests/test_sdk_build.py:282-287` (raise now at first access, not construction), `:313`, `tests/test_render.py:599` (`"self.objects ="` source-assert gone), `:646-648` (raise text). Add a render-level lazy-behavior assertion. (Docs/smoke confirmed unaffected — no `Client` instantiation there.) *Test: rendered composer defers handle build + the required-header raise to first access; constructing with region unset no longer raises.*

### Batch F — discoverability & discover (offline, against `fedsdk`)

- [ ] **F1 — `which` locator + did-you-mean + object summary.** A top-level `which <object>` (alias `where`/`find`) printing the object's sub-package + its full verb set (incl. `request` actions); a "did you mean: `<verb> <sub> <object>`" suggestion on a wrong/missing sub (from the IR object→sub index). *Test (fedsdk emitted CLI): `which widget` → `alpha widget show/set/del`; `show widget` (no sub) → did-you-mean.*

- [ ] **F2 — Per-object help descriptions + federated `cli discover`.** Reuse `ModelSchema.description` for a one-line description per object in the sub-group `--help`. `discover.py`: loop subs → a classification **table per sub** (unmapped flagged) and `--write-stub` → ONE federated `cli.yml.stub` with per-sub sections (D10). *Test (fedsdk): discover prints per-sub tables; the stub has `subpackages.alpha`/`.beta` sections.*

### Batch G — real prisma-access P0 (objects + incidents)

- [ ] **G1 — Author `products/prisma-access/cli.yml` (P0 subs).** `subpackages: {objects: {columns: {address: …}}, incidents: {request: {incidents_apis.search_incidents: {object: incident, action: search}}}}`. *Verify via `phantasos cli discover prisma-access` (objects 0-unmapped, incidents' `search` mapped).*

- [ ] **G2 — Real build + smoke + live.** `phantasos cli build prisma-access` (objects+incidents) emits `prisma-access-cli`; import-walk smoke; enroll prisma-access in `nox.toml [smoke]`. `nox -s smoke` green. A `live` CRUD round-trip on `objects address` (`set → show → del`) when creds+region present (skips otherwise). Confirm `show incidents incident` requires region (exit-2 unset) and `show objects address` does not.

### Batch H — wrap

- [ ] **H1 — Docs + changelog + PR.** `CHANGELOG.md` `## [Unreleased]` (federated CLI: verb→sub→object, connection fields, lazy handles). Update `.agents/context/cli-generator.md` (federation narrative) + `nox -s context`. Whole-branch review (subagent-driven final pass), then squash PR `--base develop`, **no version bump**.

---

## P1 — enroll the remaining 10 sub-packages

- [ ] Author per-sub `request:`/`columns`/`hide` deltas (~30 `request:` total) via `cli discover` stubs.
- [ ] The `ztna_connector` path: per-sub host-override gateway + its on-handle required header (the *other* `required_for` sub) — exercised end to end.
- [ ] A federated **oneOf-variant** command (`[sub, object, variant]`) if one arises post-flatten.
- [ ] Cross-sub object-uniqueness + unmapped-non-CRUD assertions exercised at full 12-sub scale.
- [ ] Full build + smoke (all 12) + a representative `live` round-trip.

## P2 — opt-in federated CLI docs (deferred)

- [ ] `cli.yml docs:` block; the IR-driven CLI docs grouped by sub-package; `cli-docs` nox gate enrollment.

---

## Testing decisions

- **A good test asserts external behavior through the emitted CLI** (`CliRunner` on the rendered project), never an implementation detail. The merge/dispatch/connection-field/registry-namespacing logic is proven on the **`fedsdk`** fixture **offline & fast** (real introspection of a real fake SDK — no boundary mock), with the alpha/beta **model-name collision** and beta's **required header** baked in so B3 + the connection-field path are pinned without the real build.
- **Prior art to mirror:** the single-spec `fakesdk` fixture + the `emit_cli`/`render_and_import` conftest helpers (`tests/conftest.py`); `test_cli_emitted_*` (behavioral through the emitted package); the SDK-docs rendered tests (slow, skip-gated) for the real-SDK smoke.
- **Slow/real:** `nox -s smoke` builds the real prisma-access CLI (P0 subs, then all 12); `nox -s live` for the CRUD round-trip.
- **Backward-compat = behavioral:** single-spec emitted-CLI tests stay green; regenerate the `ir.json`/`spec.py` content assertions for the additive field.

## Risks (from the rev-2 review)

- **Runtime federation (C2) is the bulk of the work**, not an IR tweak — budget for the ~6 `runtime.py` helpers + single-spec parity.
- **Model-registry namespacing (B2)** is an IR-shape change; the `fedsdk` collision canary catches it in P0 (it otherwise first bites in P1).
- **D6 (E1)** churns two SDK unit tests + the retry-on-first-*accessed*-sub side-effect — keep it small and well-asserted.
- **Compat is behavioral, not byte-identical** — don't pin single-spec bytes.
