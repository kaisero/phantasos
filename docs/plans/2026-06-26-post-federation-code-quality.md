# phantasos — post-federation code-quality refactor plan

- **Date:** 2026-06-26
- **Branch:** a **new `feature/<slug>` branch off `develop`**, to be cut **after the prisma-access SDK work has landed in `develop`** (user's choice — keeps this refactor off the in-flight federation branch). PR back into `develop`, squash-merge, **no version bump**, record under `## [Unreleased]`.
- **Status:** Plan — **no code changes made yet.** Deferred until the SDK work merges. Ranked, tiny-commit plan derived from a fresh whole-repo audit.
- **Method:** four parallel read-only Sonnet analysts (complexity / duplication+dead-code / tests+coverage / architecture+config), each invoking `python-pro` and running real tooling (radon, ruff C901, vulture, a real gate build). Findings de-duplicated and ranked across all four. The tests/coverage analyst was lost to a session-limit reset; its lane is covered by the architecture analyst's test findings + the gate baseline.
- **Relationship to prior work:** PR #37 (2026-06-25) already landed the previous cleanup backlog (`on_sys_path`, dead-code removal, `build_cli_ir`/`render_cli` decomposition, the `opmodel` layering-inversion fix, the `test_cli_emitted.py` split). This plan deliberately does **not** re-recommend any of that. It targets what is **still open** or **newly introduced by the 12-sub-package federated SDK**.
- **Baseline:** the offline suite is **623 passing** (verified serially). The one transient failure seen during the audit was a build race — concurrent builds writing the same shared output dir — which the developer has since fixed at the source (the `tmp_path` isolation commit). Re-baseline against `develop`'s count when the branch is cut.

---

## Problem Statement

phantasos has grown a lot — most recently with prisma-access, a federated SDK that merges 12 OpenAPI specs into one distribution. The growth has left two kinds of drag:

1. **A handful of over-complex functions** (radon CC ≥ 14, ruff `C901` ≥ 11) that are hard to extend and impossible to unit-test in isolation — the wrapper method-builder, the model-schema builder, the shared introspector, the vendor step, and the CLI column resolver. None are catastrophic (every module is maintainability-index rank A), but they concentrate the risk in exactly the functions that change most often.
2. **Several single-source-of-truth violations and silent-drift seams** — config look-up tables hand-mirrored from pydantic models, a federated slug list hand-copied into a test, a hardcoded auth-env helper that ignores the `credential_fields()` contract, dead fields/flags, and a clutch of federated config keys that aren't validated at load time (so a typo produces a silently-wrong artifact with a green build). The federated build path also has **no CI smoke coverage** at all.

The developer wants the complex monoliths reduced and the accidental duplication optimised, **without changing any user-observable behavior** (the emitted SDK/CLI artifacts and the `ir.json` contract stay byte-identical).

## Solution

A pure, behavior-preserving refactor delivered as a sequence of tiny commits, each leaving the suite green. Work proceeds in four batches, ordered low-risk → higher-risk:

- **Batch A — one-liners & dead code** (pure subtraction, no behavior change).
- **Batch B — federated hardening** (close the silent-drift seams and the CI gap the federation introduced — highest value, lowest risk, so do it first).
- **Batch C — single-source-of-truth** (derive the hand-mirrored tables from the models/config that already hold the truth).
- **Batch D — complexity decomposition** (split each god-function into named, independently-testable helpers; then turn on the CC gate so it can't regress).

The existing 622-test suite is the primary safety net (green before → green after each commit), supplemented by a focused new assertion wherever a commit creates a new seam. No new runtime dependency. No edit to any frozen oracle. No DRY across the deliberate `generator/sdk` ↔ `generator/cli` separation-of-duty boundary.

---

## Commits

Each commit is independently revertable, ends green (`nox -s gate`), and changes no user-observable behavior unless stated. Effort: XS/S/M. Risk: chance it breaks behavior or a contract.

### Batch A — one-liners & dead code (pure subtraction)

**A1. Close the `has_retry` collision-guard gap.** `load_product` injects `has_retry` into the Jinja context, but the `_AUTO_EXPOSED` guard set (which protects auto-injected context keys from being shadowed by a product's `vars:`) omits it — every other `has_*` key is listed. Add `has_retry` to `_AUTO_EXPOSED`. One line. (XS / Low) — *the product-config deep-dive already documents this as a known hole.*

**A2. Delete the dead `Override.variant` field.** `Override` (CLI `cli.yml` override model) defines `variant`, parsed and stored but never read by `classify` (the sole consumer reads only `.verb`/`.object`). No product's `cli.yml` sets it. Remove the field. (S / Low)

**A3. Delete the write-only `ParamInfo.union_members` field.** Set in `introspect` but never read in production; the real data already flows into `OperationInfo.body_fields`. Remove the field, remove its single assignment, and drop the one test assertion that only validated the dead storage. Keep the live module-level `union_members()` function untouched. (S / Low)

**A4. Drop `select_method_for_verb` from `__all__`.** It's exported but unimplemented (`# TODO(phase2)`, zero callers). Remove it from `__all__` (keep the stub function with a `# ponytail: phase2, not yet wired` marker). Stops the public API overstating itself. (XS / Low)

### Batch B — federated hardening (de-risk the in-flight federation)

**B1. Add `prisma-access` to the `nox.toml [smoke]` product list.** The 12-sub federated build — the newest, most complex path (12 OAG invocations, a libcst runtime-hoist transform, two template renders, per-handle `.models` wiring, header injection) — has **zero CI smoke coverage**; only a `@slow`/skip-without-OAG local test exercises it. Add the product so the existing OAG-provisioning smoke job builds it. Highest-impact single change here. (S / Low) — *expect the smoke job to get slower; it already provisions the jar.*

**B2. Thread `hook_mod` through the federated build.** `_build_federated` never loads `hooks.py` and never passes it to the per-sub generate call, so both the `preprocess` and `patch` hooks are silently skipped for every federated sub-package. prisma-access has no `hooks:` today (so no live bug), but the capability gap is undocumented and will silently bite the first federated product that needs a hook. Load hooks once and thread them through the sub loop; the existing hook contract already works per-sub (each sub has its own spec dict + package dir). Add a test that a federated product with a `preprocess` hook actually runs it. (S / Low)

**B3. Cross-validate `default_headers.*.required_for` slugs at load time.** A typo in `required_for: [incidentz]` passes all validation today and silently renders a *mandatory routing header* optional for every sub-package — a security-adjacent silent-wrongness. Extend the existing `subpackages`-validating model validator to reject `required_for` slugs not in `subpackages`. Add a test for the typo case. (S / Low)

**B4. Validate `docs.showcase_subpackage` at load time.** An invalid showcase slug currently fails deep in the build with a misleading `ModuleNotFoundError` and no attribution. Validate it against the loaded sub-package slugs in `load_product`, raising a clear error naming the bad key and the valid set. Add a test. (S / Low)

**B5. Validate "federated product requires `auth:`" at load time.** `_render_shared_auth` raises mid-build if a federated product lacks a top-level `auth:` block; move that assertion one layer earlier into the model validator so it fails at parse time with a clear message. Add a test. (S / Low)

**B6. Derive the federation test's slug list from `sdk.yml`.** `test_sdk_build.py` hard-codes the 12 federated slugs (`_ALL_SLUGS`) — a hand-typed mirror of the `subpackages:` list, used in four assertions. Replace the literal tuple with a derivation via `load_product("prisma-access")` (a pure file read). Onboarding a 13th sub then edits one file, not two. *Note: by the time this branch is cut, the `_ALL_SLUGS`/hoist-shape assertions and the `tmp_path` isolation fix will already be in `develop` (they were WIP during the audit); this commit builds on that committed form.* (S / Low)

### Batch C — single-source-of-truth (derive from the real source)

**C1. Build `_auth_env_vars` from the `credential_fields()` contract.** The scaffold-context helper hardcodes four `ScmOAuth` attribute names (`client_id_env`, …) with or-defaults that hide failure; every other call site already uses `AuthComponent.credential_fields()`. Rewrite it to iterate `credential_fields()` (reproducing the exact existing examples via `name.replace('_','-')`). When a second auth strategy is added, this helper then stays correct instead of silently emitting wrong env-var docs. Behavior-identical for the current SCM products — guard with a golden/scaffold test. (S / Low)

**C2. Derive the generated-CLI config look-up tables from `model_fields`.** In the `config.py.jinja` template, `_ENV_MAP`, `_BOOL_PATHS`, `_INT_PATHS`, and `effective_dict()` are four hand-typed mirrors of what `CliConfiguration.model_fields` already carries (`_known_config_paths()` already derives the same path set). Replace each with a small comprehension over `model_fields`. Collapses the documented "6-step recipe" for adding a CLI option toward the 2 steps a test already enforces, and removes a silent-by-omission drift class. This is a **template** change — emitted into every generated CLI and guarded by golden + defaults-sync tests, so verify the emitted output is byte-identical. Do it as four sub-commits (one table at a time) so any golden diff is isolated. The `default_config.yml.jinja` env-var doc comments remain a manual mirror for now (a separate Jinja-loop task) — leave a marker noting it. (M / Low)

### Batch D — complexity decomposition (one function per commit; CC gate last)

Each decomposition is extract-function only (no logic change), guarded by the existing tests for that path, with one new focused assertion on the extracted seam.

**D1. Split `_build_method` (wrapper builder, CC 18/16 — the worst offender).** Extract `_op_to_binding` (one op → its `Binding` + return-import + body-model type) and `_union_param_views` (one op's params → deduped non-body `ParamView`s + body `ParamView` + imports). `_build_method` becomes a ~20-line assembler; CC ≈ 7. Two commits + a self-check asserting `_op_to_binding` returns the right `requires` set for a fixture op. (S / Low)

**D2. Split `_model_to_schema` (model-schema builder, CC 20).** The `if members:` (oneOf wrapper) and `else` (plain model) branches share zero state. Extract `_oneof_schema` and `_plain_schema`; the parent becomes a 4-line dispatch (CC ≈ 2). Each helper independently testable. Two commits. (S / Low)

**D3. Decompose `_introspect` (shared opmodel, CC 16/12).** Extract `_extract_body_fields(base, ns)` (the 3-deep body-field/oneof-member walk) and `_classify_param(...)` (the body/required/query location-assignment + `ParamInfo` construction). The param loop flattens; CC ≈ 9. This is the only `C901` violation in a module shared by both build stages, so it must shrink before the gate (D6) can go on. Two commits. (S / Low)

**D4. Extract `_write_core_components` from `vendor` (SDK render, CC 14/13).** Pull the auth/pagination/errors/facade-pass-1/retry/include writing — including the prisma-access `suppress_auth` rebinding — out of `vendor`, leaving a body where the auth mode is visible at one call site and isolated from the two-pass facade logic. CC ≈ 7. One commit. (S / Low)

**D5. Decompose `_resolve_columns` (CLI column resolver, CC 15/14).** Hoist the `_rep_op` closure to a module-level `_representative_op`; extract `_obj_response_fields` (the two-pass obj-fields build) and `_column_specs_per_object` (validation + per-object resolution). The parent becomes a ~10-line orchestrator; CC ≈ 4. Two commits. (S / Low)

**D6. Turn on the `C901` complexity gate.** Add `"C901"` to `ruff.lint.select` with `[tool.ruff.lint.mccabe] max-complexity = 15`. After D1–D5 the only function that would still trip a stricter threshold is gone; at 15 the gate catches genuine future outliers without demanding more immediate work. (Optionally tighten to 10 later with explicit `# noqa: C901` markers on any remaining breadth-only orchestrators like `load_product`/`build_cli_ir`, documenting the debt.) (XS / None)

---

## Decision Document

- **Scope axis:** whole-repo re-audit (developer's choice), de-duplicated in synthesis against PR #37 so the plan never asks to redo finished work. Primary scope is `src/phantasos/**`, the federated build/config surface, and `tests/test_sdk_build.py`.
- **Landing target:** a **new `feature/<slug>` branch off `develop`, cut after the prisma-access SDK work merges to `develop`** (developer's choice — revised from "fold into the prisma-access branch"). Because the refactor then sits on its own branch, it can be a single focused PR or split across a few; recommended ordering is still **Batch B first** (highest value), then A, then C, then D. Batch D (complexity decomposition) is the natural slice to land as a separate follow-up PR if the first one grows.
- **Behavior-preserving contract:** the emitted SDK/CLI artifacts, the `ir.json`/`spec.py` serialized contract, and all CLI exit codes/output stay byte-for-byte unchanged. Every Batch-D change is extract-function only.
- **Decomposition style:** plain module-level functions, never new classes — matches the choice PR #37 already made for `build_cli_ir`.
- **Modules touched:** `productconfig` (validators + `_AUTO_EXPOSED`), `generator/cli/cliconfig` + `classify` + `scaffold_context`, `generator/opmodel/inventory` + `introspect`, `generator/sdk/wrapper` + `render` + `build`, the `config.py.jinja` template, `nox.toml`, `pyproject.toml` (ruff), and `tests/test_sdk_build.py`.
- **New single sources of truth established:** sub-package slug list = `sdk.yml subpackages:` (B6); generated-CLI config env/bool/int maps = `CliConfiguration.model_fields` (C2); auth env-var docs = `AuthComponent.credential_fields()` (C1).
- **Federated config keys gain load-time validation:** `default_headers.*.required_for`, `docs.showcase_subpackage`, and the federated `auth:` requirement (B3–B5) — converting three silent/late failures into clear parse-time errors.
- **Pitfalls cross-reference (from the prior architecture review):** the provenance-version lie is already **fixed** (now `importlib.metadata.version`); Pitfall 3 (auth↔spec 401) is architecturally **resolved for federated products** via the unconditional-bearer client — so it is *not* re-opened here. Flexibility gaps F2/F3/F5 (param-location loss, single auth strategy, envelope detection) are **not concrete on this branch** because no CLI is generated for prisma-access yet — deliberately out of scope.

## Testing Decisions

- **What a good test is here:** asserts *external behavior through the emitted/loaded artifact*, never an implementation detail. A refactor test proves the public output is unchanged; a hardening test proves a bad config now raises at the right layer with a clear message.
- **Primary safety net:** the existing 622-test offline suite, run via `nox -s gate` after every commit (green before → green after). Behavior-preserving commits add **no** new test beyond a single seam assertion.
- **New tests (small, behavioral, mirroring existing prior art):**
  - B2: a federated product whose `hooks.py` defines `preprocess` actually runs it (mirror `products/posture/hooks.py` + existing build tests).
  - B3/B4/B5: load-time validation rejects a bad `required_for` slug / bad `showcase_subpackage` / missing federated `auth:` — `pytest.raises(ValueError, match=...)` against `load_product`/`ProductConfig`, mirroring the existing `_exactly_one_spec_mode` validator tests.
  - C1/C2: scaffold/golden tests confirm the emitted auth-env docs and the generated `config.py` are byte-identical after deriving from the models.
  - D1–D5: one focused assertion per extracted seam (e.g. `_op_to_binding` returns the right `requires` set), on top of the unchanged path tests.
- **Test-policy compliance (repo rule):** real dependencies; never mock the system-under-test or the prisma-browser API boundary. None of these commits introduce a mock.
- **Coverage gap noted (not fully audited — the coverage analyst was lost to a session limit):** the federated build paths (`_build_federated`, `hoist_runtime`, `_render_shared_auth`, `_render_composer`) are exercised only by the local `@slow` test. **B1 (smoke coverage) is the concrete remediation;** a follow-up coverage-distribution pass on those modules is recommended once B1 lands.

## Out of Scope

- **Any DRY across `generator/sdk` ↔ `generator/cli`** (`examples.py`, the two `_command_view`s, parallel classify logic, the `_VERB_PREFIXES`/`_CLI_VERB_PREFIXES` `update_` divergence) — deliberate separation-of-duty.
- **`StrEnum`-ifying `Verb`/`SubVerb`/`FlagKind`** — they serialize verbatim into the frozen `ir.json`/`spec.py` contract.
- **Converting the prefix-loop classifiers to `match`** — already data-driven; `str.startswith` has no clean `match` form.
- **Frozen oracles** (`.claude/harness.toml` `protected_globs` incl. itself, `tests/fixtures/fakesdk/**`, `tests/golden/**`) — never edited; surface concerns for a human.
- **Flexibility gaps F2/F3/F5 and Pitfalls 1b/1c/2/5** (param-location loss, auth-strategy registry, envelope detection, hint-swallowing, the freshness guard, CODEOWNERS/`live.yml`) — pre-existing or not-yet-concrete; they belong to a separate *hardening/enrolment* effort, not this code-quality pass.
- **`load_product` / `build_cli_ir` / `render_cli` / `build_cli_docs_context` decomposition** — their CC is breadth (sequential orchestration), not tangled nesting; leave unless touched. The federation additions to `load_product` follow the existing flat pattern.
- **`GeneratorConfig.library` / `oneof_discriminator_lookup`** — live OAG flags (flow into the jar invocation + a scaffold template), not dead knobs, even though no product overrides them.
- **`cli_operations(registry_attr=…)`** — an always-default parameter; removing it churns a widely-imported signature for negligible gain. Deferred.
- **The `default_config.yml.jinja` env-var doc comments** — a manual mirror that needs a separate Jinja-loop change; left with a marker (part of C2's note).

## Further Notes

- **Gate red during the audit was a build race, not a regression.** Two read-only analyst builds plus the Stop-gate wrote the same shared sibling output dir (`/home/ubuntu/git/prisma-access-sdk/`) concurrently; the gate observed a transient mid-build moment where a per-sub `objects/api_client.py` existed before the runtime-hoist step removed it. Post-drain the output tree is clean (only `_runtime/api_client.py`, zero per-sub clients) — the federated build is correct serially. *Lesson worth a follow-up: the federation tests build into a fixed shared path; isolating that into a `tmp_path` per test would make the suite parallel-safe.*
- **Verification per commit:** `UV_PROJECT_ENVIRONMENT=$HOME/.tmp/cq uv run nox -s gate`; before declaring a batch done, `... nox -s live` (skips without creds). After a batch that alters a subsystem, update its `.agents/context/*.md` deep-dive and run `nox -s context` (`-- --check` must pass).
- **Source-of-evidence:** radon CC/MI, `ruff --select C901` (5 violations today: `_build_method` 16, `_resolve_columns` 14, `vendor` 13, `_introspect` 12, `load_product` 11), vulture@80 (4 hits, all confirmed false positives — mandatory libcst callback params).
