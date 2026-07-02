# Phantasos — refactoring gaps & top-5 rewiring report

- **Date:** 2026-07-02
- **Tree analyzed:** `feature/lazy-cli-command-loading` @ `1c5305a` (superset of the #41/#42/#43 federated-CLI lineage merged to `develop`; the lazy-loading work is orthogonal to every finding here).
- **Status:** Findings report — **no code changes made.** Each top-5 item below is written as a plan seed: generate one implementation plan per item.
- **Method:** one verification lane re-checked all 24 open items from the four prior reviews against today's tree; three fresh-eyes lanes reviewed the owner's three stated doubts (per-product config / testing / mental model) with a refactoring lens. Headline *new* claims were re-verified first-hand by the synthesizer (Jinja `undefined` policy, the stale `hide:` rows, the gate's slow-build cost — all confirmed).
- **Relationship to prior reviews:** builds on `2026-06-25-repo-cleanup-findings.md` (landed via #37), `2026-06-25-architecture-pitfalls-review.md`, `2026-06-26-post-federation-code-quality.md` (batches A–D, still unlanded), and `2026-07-01-phantasos-architecture-ultrareview.md`. Overlaps are absorbed and credited per item; this report adds the plans-vs-reality scoreboard plus genuinely new findings (gate cost inversion, CI-invisible real-artifact ring, Jinja strictness split, dead/half-validated cli.yml surface, layering half-refactor).

---

## 0. Direct answers to the three doubts

**"Is the way config is specific per product sound?" — Yes at the core, frayed at the edges.** The declarative `extra="forbid"` sdk.yml/cli.yml pair over one shared loader is principled: the CLI *derives* auth, error envelopes, and connection headers from the SDK config instead of re-declaring them (`cli.py:153-155`), the same two files scaled to a 12-sub federated product with no new mechanism, adem builds a CLI with zero cli.yml, and the only `hooks.py` in the repo is 4 lines. The sdk.yml-vs-cli.yml op-mapping split is *not* a leak — SDK method naming and CLI command naming are genuinely different decisions that demonstrably diverge (ztna: `start_offboarding` vs `offboard`). What's unsound is edge discipline: dead accepted-but-ignored keys, half-and-half typo validation (with stale rows already shipping), and hand-mirrored derivable tables. → Items 4.

**"Is the testing sound?" — The model is; the wiring is inverted.** There is a coherent five-ring ladder (generator unit → emitted-on-fixture behavior → emitted-on-real-artifact behavior → build/install/docs sessions → live tenant), and the test *content* honors the repo's policy. But ring selection is spread across five unrelated mechanisms, the ring that catches OAG/fixture drift never runs in CI, the docs-fidelity session runs in no CI job, and the "fast" Stop-hook gate silently runs the *slowest* tests in the repo on every agent stop. The strongest guarantee (frozen oracles) is enforced on zero real files. → Items 1 and 2.

**"Is the overall mental model sound?" — Yes, with one dominant incoherence pattern.** The two-stage model (build a standalone artifact, reflect over it) is real and enforced where it matters: opmodel's import graph is acyclic, `spec.py` ≡ `ir.py` by construction, federation is one pipeline-propagated predicate per stage. The recurring slop is **"one contract, many ad-hoc access paths"**: because `cli/ir.py` ships verbatim into every emitted CLI, shared vocabulary gravitates there, and the codebase grew four divergent workarounds to reach it (an upward import from the base layer, an unguarded byte-copy, a third partial copy in a template, load-bearing "back-compat" shims). A second pattern: mechanically identical engines with silently different strictness (lenient vs Strict Jinja `undefined`; in-process vs subprocess artifact access). And the read-first doc (`index.md`) states an invariant that is false for CLIs. → Item 5 + the docs-truth quick win.

---

## 1. Plans-vs-reality scoreboard

Shipped since the reviews were written: #37 (cleanup tiers 1–2), #38 (federated SDK), #41/#42/#43 (federated CLI P0/P1/P2 + federated live smoke), lazy CLI command loading (this branch). Against that, the 24-item open-findings ledger verified today:

**1 FIXED** (provenance stamp via `importlib.metadata`, #38) · **2 PARTIAL** (declarative `normalize_operation_ids` exists but federated-only; prisma-access enrolled in `[live]`/`[cli-docs]` but not `[smoke]`) · **21 OPEN** · 0 overtaken.

Every item from post-federation batches A–D is still open (the plan itself is deferred-by-design until now — this is the "biggest gaps open" answer in one line: **the entire hardening/SSoT backlog has had zero movement while three feature waves landed on top of it, widening several items**). Full verified table: Appendix A.

---

## 2. Top 5 — one plan per item

### Item 1 — Rewire the verification ladder: the strongest checks run nowhere, the slowest run on every stop

> **✅ IMPLEMENTED** on `feature/architecture-cleanup` (2026-07-02, 7 commits off `develop`@7ce6382). Gate deselects the 2 slow builds; one `real_sdk` fixture+marker replaces the 12 per-file `REAL_SDK` constants (ring auto-tagged, `-m real_sdk` selects 55); smoke runs the ring after building (+ prisma-access enrolled); new `sdk-docs` CI job; live downgraded to advisory (no live.yml). Bonus: SDKs carry a `.build-stamp` (generator SHA) and the fixture skip-loudly when the generator changed since the build (diff-based, not exact-SHA). Verified: full gate green (729 passed, ring skips-stale as designed), `nox -s smoke` green (all 3 SDKs built, ring 55/55 passed fresh, stamp written). Not yet PR'd to `develop`.

**Problem (all verified today).**
- The Stop-hook gate runs bare `pytest -q` (`noxfile.py:164`) with a docstring demanding it "stay fast" — yet `tests/test_sdk_build.py:90` (`@slow`, full prisma-browser OAG build, runs whenever the sibling SDK exists) and `:112` (full 12-spec federated build, runs whenever specs + toolchain are present) are selected by it. On the provisioned dev machine both conditions hold, so **every agent stop pays multi-minute Java builds**; in CI, where the skipifs fire, the same tests never run. `pyproject.toml:177` even documents the deselect flag nobody passes.
- Ring 3 — the ~60-80 tests that exercise the *real OAG-built* SDK (`test_cli_emitted_real.py`, `test_cli_dispatch_matrix.py`, `test_sdk_wrapper.py`, `test_sdk_oneof_real.py`, `test_cli_discover_golden.py`, …) — is keyed to an unversioned sibling dir via 12 independently-declared `REAL_SDK` constants and **skips silently in every CI run forever**. It is the only ring that catches OAG-output/fixture drift (the exact class the fakesdk ring cannot see), and locally it happily tests a stale artifact (no build stamp).
- `nox -s sdk-docs` and its `[[sdk-docs.assert]]` fidelity checks (the guards for the hard-won "docs show payload, not scaffolding" invariant) appear in **no CI workflow**. `[smoke]` still lacks prisma-access (`nox.toml:16`). `noxfile.py:244` still advertises a `live.yml` CI gate that does not exist.

**Why now.** This is the "green build ≠ verified" theme's wiring layer: cost and coverage are exactly inverted, and it silently taxes every agent turn. Fixing it also delivers the only worthwhile part of the ultrareview's OAG-drift vector (#4): once ring 3 runs after the CI smoke build, `test_sdk_oneof_real.py` *is* the real-build behavioral assert — no new test needed.

**Plan seed.**
1. Gate: `pytest -q -m "not slow"` (one line; the two builds already have homes in `smoke`/CI).
2. One `real_sdk` conftest fixture + marker replacing the 12 `REAL_SDK` constants and ~15 copy-pasted skip prologues; makes the ring explicitly selectable (`-m real_sdk`).
3. CI: append a `pytest -m real_sdk` step to the existing smoke job (it already builds prisma-browser into the sibling path and caches the JRE); add an `sdk-docs` job cloned from the cli-docs job; add `"prisma-access"` to `[smoke]`.
4. Stamp the built sibling SDK with the generator git-sha; ring-3 tests warn/skip-loudly on mismatch.
5. Either wire a scheduled `live.yml` (creds as secrets) or fix the `noxfile.py` docstring to "advisory/local-only".
**Acceptance:** gate wall-time drops to pre-build levels on a provisioned machine; CI run shows ring-3 + sdk-docs green; zero `REAL_SDK` constants left outside conftest.
**Absorbs:** ultrareview #5 + #4-core, post-federation B1, pitfalls P5 (live.yml half). **Effort S–M. Risk: low (+2–4 min on one CI job).**

### Item 2 — Re-arm the oracle-protection harness (active regression)

**Problem.** `.claude/harness.toml:7-12` protects only `tests/acceptance/**` (directory does not exist) plus the harness's own files. Every real oracle is unprotected and freely editable today: both live-CRUD oracle templates (`products/prisma-browser/overrides/tests/test_sdk_crud_live.py.jinja`, `products/prisma-access/overrides/tests/test_scm_crud_live.py.jinja`), the scaffold's `tests/test_federated_live.py.jinja`, `tests/test_cli_prisma_access_e2e.py`, and — widened by this review — `tests/golden/**`, `tests/fixtures/{fakesdk,fedsdk}/**`, and the `nox.toml` content assertions. Worse, `tests/test_harness_hooks.py:36-38,134-136` tests an *inline* glob that is not in the real config — so the harness's own suite stays green while the deployed config protects nothing. The working glob existed at day one and was dropped in the #38 squash-merge (regression, not design).

**Why now.** The harness is the repo's reason-to-trust-agent-work; it is currently a no-op, and two feature waves have added new unguarded oracles since. Cheapest item on the board with the highest trust payoff.

**Plan seed.** Note: `harness.toml` is itself a frozen oracle — **the glob edit is the human's move**, the agent delivers everything around it.
1. (Human) restore/extend `protected_globs`: `products/*/overrides/tests/test_*_live.py*`, `src/phantasos/scaffold/tests/test_federated_live.py.jinja`, `tests/golden/**`, `tests/fixtures/**`; decide the CLI e2e file in/out; delete the dead `tests/acceptance/**` row.
2. One offline meta-test that loads the **real** `.claude/harness.toml` and asserts (a) every glob matches ≥1 existing path, (b) every shipped `*_live.py.jinja` matches some protected glob — closes the bug-class (a future product cannot ship an unguarded oracle).
3. Fix `test_harness_hooks.py` to stop baking its own glob list.
4. `.github/CODEOWNERS` over the protected globs (the documented, never-built server-side net).
**Acceptance:** meta-test red if any glob is dead or any live oracle unguarded; freeze hook actually blocks an edit to a `*_live.py.jinja`.
**Absorbs:** ultrareview #1, cleanup #19, pitfalls P5 (CODEOWNERS half). **Effort XS–S. Risk: none.**

### Item 3 — Collapse the single-vs-federated build fork's silent asymmetries

**Problem (verified open, widened by #42).** `_build_single` and `_build_federated` are two hand-maintained pipelines sharing only `clean` + `_generate_one`:
- Federated never calls `_load_hooks` and passes no `hook_mod` (`build.py:180-253`) → a federated product's `hooks.py` preprocess/patch hooks are **silently skipped** (post-federation B2, still open).
- Federated discards `_patch_stats` (`build.py:243`); no patch-count floor is asserted anywhere — an OAG anchor miss no-ops green.
- Generic, self-gating spec fixes are mode-stranded: `flatten_scm_bodies`/`relax_readonly_required`/`translate_property_patterns`/`normalize_operation_ids` run **federated-only** (`build.py:220-235`); the declarative `transforms:` block (`hoist_items`/`tag_operations`) runs **single-spec-only** (`:140-154`). A single-spec product with a `\p{}` regex ships a broken validator green; a federated product's `transforms:` is a silent no-op. #42 *deepened* this split by adding `translate_property_patterns` to one side only.

**Why now.** This is the core SDK-gen seam, the most-corroborated still-open correctness gap (ultrareview #3 ⊃ B2), and every new generic spec-fix added since has landed on exactly one side — the fork is actively accreting divergence.

**Plan seed.** Deliberately NOT a full pipeline unification (the per-sub build-state accumulation is genuinely federated — conceded in the ultrareview arbiter notes).
1. Thread `_load_hooks` per-sub through `_build_federated` (one `hook_mod=` argument); test: a federated product with a `preprocess` hook actually runs it.
2. Extract the *generic, self-gating* transform list into one shared sequence run in **both** modes (each is a no-op when its marker/pattern is absent); make declarative `normalize_operation_ids` available to single-spec products (this is the pitfalls-F1 classification primitive going generic).
3. Stop discarding `_patch_stats`; assert a non-zero patch floor when the corresponding markers are present (serves the OAG-drift vector too).
**Acceptance:** a parametrized test proving each generic transform fires in both modes; hook-runs test green; patch-floor assert red on a synthetic anchor-miss.
**Absorbs:** ultrareview #3, post-federation B2, part of #4 (`_patch_stats`), pitfalls-F1 (partial→generic). **Effort M. Risk: medium (touches the build seam; gate + smoke + `nox -s live` before declaring done).**

### Item 4 — Make config validation symmetric and derive the hand-mirrors

**Problem (all verified today).** The config layer's failure behavior is inconsistent in ways that already shipped drift:
- **Dead surface:** `cli.yml` `settings:` and `custom:` are declared, documented in the module docstring, and consumed by nothing (`cliconfig.py:80-81`; the emitted `custom/` package is scaffolded unconditionally regardless). `extra="forbid"` implies "validates ⇒ works"; these validate and do nothing.
- **Half-and-half validation:** `defaults` and `columns` keys are fail-loud validated (`classify.py:392-409,562-565`) while `hide`/`request`/`override`/`variants` keys silently no-op (`classify.py:609-621`). In-tree proof: 5 of prisma-browser's 14 `cli.yml hide:` rows (`cli.yml:71-79` — the cloud-storage PUT + 4 asset uploads) are **dead today**, because `sdk.yml:74-78` hides those ops at the SDK layer so they never reach the CLI inventory. Nothing reports this. Meanwhile sdk.yml `operations:` keys ARE validated (`wrapper.py:57-77`).
- **Slug holes beside a validated twin:** `default_headers.*.required_for` is never checked against subpackage slugs (a typo silently demotes a mandatory routing header), `docs.showcase_subpackage` fails deep as an ImportError — while neighboring `live_smoke` slugs are build-validated fail-loud (`build.py:390-406`). Same slug space, three failure behaviors.
- **Live mirror drift:** `_AUTO_EXPOSED` still omits `has_retry` (`productconfig.py:283-303` vs `:366`) — the guard structurally cannot protect the one key federation added. In the emitted CLI, `_ENV_MAP`/`_BOOL_PATHS`/`_INT_PATHS`/`effective_dict()` remain four hand-typed mirrors of what `_known_config_paths()` already derives from `model_fields` in the same template (`config.py.jinja:88-106,261-276,343-354`). `scaffold_context._auth_env_vars` still hardcodes ScmOAuth attrs, bypassing the `credential_fields()` contract; root cause is that `LoadedProduct`'s component slots are typed `Any`, so every consumer duck-types (`productconfig.py:274-278`).

**Why now.** This is the config-doubt answer made actionable: the core is sound, so the plan is pure edge-hardening — and the drift is no longer hypothetical (stale rows and the `has_retry` hole are in-tree).

**Plan seed.**
1. Delete `settings`/`custom` from `CliConfig` (the forbid-model then rejects them loudly).
2. `_validate_delta_keys` over the same ops index, mirroring `_validate_defaults`, covering `hide`/`request`/`override`/`variants`; fix the 5 stale prisma-browser rows it flags (they're documented-deferred ops — likely: move the dedup note into sdk.yml, drop the dead cli.yml rows).
3. Slug cross-checks for `required_for` + `showcase_subpackage` in the existing `ProductConfig` validator (slug set already in-model). Move the federated-requires-`auth:` assert to parse time.
4. `_AUTO_EXPOSED` → `reserved = set(context)` captured immediately before `context.update(cfg.vars)` (deletes the literal, closes `has_retry`).
5. Derive `_ENV_MAP`/bool/int paths/`effective_dict` from `model_fields` inside the template (≈45 mirrored lines deleted; guarded by the existing defaults-sync + golden tests) — or, minimum bar, add one drift test per mirror.
6. `_auth_env_vars` ← `credential_fields()`; type the `LoadedProduct` component slots (`AuthComponent | CustomComponent | None` etc.); add a `Verb` Literal on CLI `Override.verb`, dropping the `cast`.
**Acceptance:** a typo'd key in ANY cli.yml section and a typo'd slug in ANY sdk.yml cross-ref fail at load with a message naming the valid set; adding a runtime-config field requires touching exactly the 2 test-enforced places.
**Absorbs:** ultrareview #2, post-federation A1/A2/B3/B4/B5/C1/C2, pitfalls P4. **Effort S–M (6 small commits). Risk: low.**

### Item 5 — Finish the layering refactor: one home for the shared contract, one strictness per mechanism

**Problem (verified today).** The `opmodel` extraction (#37) stopped halfway, and the "same mechanism" promise breaks in two places:
- **Contract gravity:** the shared host layer still imports UP into stage-2 (`config.py:13` → `generator.cli.ir` for `CredentialField`/`ErrorEnvelope`); `sdk/build.py:398` and `sdk/docs.py:22` import `generator.cli` for inventory/`cli_operations`; the sanctioned alternative — `vocab.py` ↔ `ir.py` byte-duplication — has its MUST-stay-in-sync invariant enforced by comments only (zero tests reference `opmodel.vocab`), and the lazy-loading template added a third, subset `_VERBS` copy (`app.py.jinja:40`). The "back-compat" shims are the *majority* import path inside `cli/` itself, and `sdk/docs.py:173-186` hand-rolls a fourth copy of the exact `sys.path` dance `on_sys_path` was created to kill.
- **Strictness split (new, security-adjacent):** the SDK component/product Jinja envs have **no** `undefined=StrictUndefined` (`sdk/render.py` `_env()` and `product_env` — verified) while scaffold and CLI envs hard-fail (`scaffold.py:46`, `render_cli.py:334`). A typo'd context key renders **silently empty Python** in exactly the most security-relevant emitted files (auth.py, facade, the federated composer/`_auth.py`), but fails loud everywhere else.

**Why now.** This is the mental-model doubt made concrete: every one of these is a place where a reader's natural assumption ("the base never imports up", "the copies are guarded", "same engine ⇒ same failure mode") is false. Each is small; together they're the difference between a documented architecture and an actual one.

**Plan seed.**
1. `undefined=StrictUndefined` on both SDK envs; run smoke/gate to surface (and fix) any template leaning on leniency. (First commit — independent and highest value.)
2. Move `CredentialField`/`ErrorEnvelope` canonically into `opmodel` (byte-copies stay in `ir.py`, which must remain self-contained as `spec.py`); point `config.py` at opmodel. Move `cli_operations` (pure wrapper-inventory introspection) into opmodel beside `introspect()`, re-export from `cli.classify`.
3. ONE sync test: `typing.get_args` equality for the Literal vocab + `model_fields` equality for the copied models (covers `vocab.py`, `ir.py`, and the new copies).
4. Migrate cli-internal + `sdk/docs.py` imports off the shims to `opmodel` directly; shims remain for external/test compat. Replace `sdk/docs.py`'s hand-rolled path dance with `on_sys_path` (3 lines).
5. Template nits while there: derive the emitted verb-group list from `{c.verb for c in _REGISTRY}` instead of the `_VERBS` literal.
**Acceptance:** `grep` shows zero `generator.cli` imports from `config.py`/`productconfig.py`/`generator/sdk/` (docs/classify re-export shims excepted); sync test red on any drifted copy; a deliberately typo'd key in a component template fails the build.
**Absorbs:** cleanup #11 remainder, ultrareview also-ran (config.py up-import), post-federation "guard-test not refactor" note (the sync test IS that guard). **Effort M. Risk: low-med (StrictUndefined may surface latent misses — that is the point; needs one full smoke pass).**

---

## 3. Below the cut — quick wins & fold-ins

| Win | Evidence | Where it lands |
|---|---|---|
| Docs-truth pass: `index.md` "disposable artifact" invariant is false for CLIs (`main.py`/`hooks.py`/`custom/` are emitted-once, hand-owned — `render_cli.py:26,632`); `index.md` repo map omits `generator/opmodel/` entirely; 6 more stale statements | Appendix B | One XS docs-only PR, or fold into whichever item lands first (repo rule: update deep-dives per subsystem change) |
| `showcase_resource` (sdk.yml) vs `showcase_object` (cli.yml) — same concept, two names; prisma-access sdk.yml apologizes for it in a comment | `productconfig.py:70` vs `cliconfig.py:66` | XS pydantic alias now; `sdk_resource` IR-field rename only at a deliberate ir.json-breaking window |
| Scaffold dest-collision guard: `foo.md` + `foo.md.jinja` silently race on sort order + whitespace-gate | `scaffold.py:49-57` | 4-line assert; fold into item 5 |
| Session-scope the `emitted` fixture (render once, `copytree` per test) — it currently re-renders the full CLI for every one of ~160 uses | `conftest.py:209-246` | S, own micro-PR; biggest offline-suite speedup after item 1's gate fix |
| One `isolated_home` fixture (HOME + env + `load_config.cache_clear()`); migrate the 6 files still hand-rolling sys.modules purges | 79 `setenv("HOME")` sites, 14 scattered `cache_clear()` | S, mechanical; kills the order-dependent-flake class |
| Test-subject renames: `tests/cli/`→`tests/cli_docs/`, `test_smoke.py`→`test_sdk_smoke_module.py`, `test_cli.py`→`test_phantasos_cli.py`; upgrade `test_crud_live_template.py` from source-string grep to import-and-inspect (its federated sibling shows how) | testing lane #8 | XS–S |
| Promote the SDK `README.md.jinja` into the builtin scaffold (3 products hand-copy it; 2 byte-identical; the CLI side already ships one at framework level) | `find src/phantasos/scaffold` vs `generator/cli/cli_overrides/` | XS–S |
| Fail-loud one-liners still open from pitfalls: `get_type_hints` swallow (`opmodel/introspect.py:213-216`), `_discover_resources` silent `[]` (`sdk/render.py:31-43`), `urlopen` no timeout (`provision.py:40`), stage-freshness guard (SPEC_VERSION vs spec, pitfalls P2) | ledger S5–S8 | Fold S5/S6 into item 3's fail-loud pass; S7/S8 standalone XS |
| Lazy-loading hardening: `_META` completeness and leaf-kwarg parity are convention-plus-tests; dead `load`/`backup` verbs in the frozen vocab are unreachable by any classifier | `app.py.jinja:111-120,216-219`; `vocab.py:18` | Comment-or-remove at the same contract window as the IR rename |

## 4. Deliberately NOT in the top 5

- **OAG shared-constant re-plumbing + mustache diff-guard** (ultrareview #4 body): subsumed — item 1 puts the real-build behavioral tests in CI, which is the one red gate an OAG bump actually needs; the constants are cosmetic.
- **Full single/federated pipeline unification**: per-sub state (`host_overrides`, `header_declared_by`) is genuinely federated; item 3 takes the safe subset only.
- **Flexibility gaps F2–F5** (param location, auth/pagination registries, envelope heuristic): enrollment-driven product work, not refactoring debt — build them when adem/ngts/incidents CLIs are actually scheduled.
- **Any DRY across `generator/sdk` ↔ `generator/cli`**: deliberate separation-of-duty (owner decision, re-confirmed by all lanes — the `examples.py` twins have not drifted in meaning).
- **Federated CLI registry collision**: refuted in-tree (slug-qualified merge + regression test); stays dead.
- **hooks.py "undermining declarative config"**: it doesn't — one 4-line hook across three products is a proportionate escape hatch. YAGNI on promoting it.

## 5. Checked and sound — leave alone (consolidated from all lanes)

opmodel's acyclic import graph · `spec.py`≡`ir.py` by construction · federation as one propagated predicate per stage · the scaffold engine's single render path (modulo the collision guard) · `flags.py` shared by render+docs with a drift test (the parity exemplar) · smoke's venv caching (fresh `project_dir` always front-loaded) · the freeze/fast-gate hook *mechanics* (fail-closed/fail-open asymmetry, subprocess-tested — only the config is vacuous) · `cli_isolated_smoke.py`'s clean-venv gate · `nox -s live`'s fail-loud-on-empty · CI's `uv lock --check` · `test_cli_prisma_access_e2e.py` (best-written module in the suite) · dispatch mocks asserting exact call targets at the CLI→facade seam · the component registries (`credential_fields()` enforced at class-definition) · CLI deriving auth/errors/headers from sdk.yml (real SSoT) · adem's zero-cli.yml scale-down · host CLI exit-code contract · provisioning/preprocess/release.yml (unchanged verdict since June).

---

## Appendix A — Verified ledger (2026-07-02, tree `1c5305a`)

| # | Item (origin) | Status |
|---|---|---|
| H1 | protected_globs matches no real oracle; harness test bakes own glob (ultra #1) | **OPEN** (`.claude/harness.toml:7-12`) |
| H2 | No live.yml / CODEOWNERS; noxfile claims CI gate (P5) | **OPEN** |
| H3 | `[smoke]` lacks prisma-access (B1) | **OPEN** (`nox.toml:16`; enrolled in live/cli-docs) |
| H4 | goldens/fixtures unprotected (cleanup #19) | **OPEN** |
| C1 | `_AUTO_EXPOSED` omits `has_retry` (A1) | **OPEN** (`productconfig.py:283-303` vs `:366`) |
| C2 | Runtime-config hand-mirrors (C2/P4) | **OPEN** (`config.py.jinja:88-106,261-276`) |
| C3 | `_auth_env_vars` hardcodes ScmOAuth (C1) | **OPEN** (`scaffold_context.py:23-35`) |
| C4 | Dead `Override.variant` (A2) | **OPEN** (`cliconfig.py:32`) |
| C5 | CLI Override.verb untyped; delta keys unvalidated | **OPEN** (`cliconfig.py:31`, `classify.py:609-621`) |
| C6 | required_for/showcase_subpackage/auth-at-parse unvalidated (B3/B4/B5) | **OPEN** |
| C7 | `CustomComponent` extra="allow", no users | **OPEN** (`productconfig.py:223-246`) |
| S1 | Federated build skips hooks (B2) | **OPEN** (`build.py:180-253`) |
| S2 | `_patch_stats` discarded, no floor | **OPEN** (`build.py:243`) |
| S3 | Generic transforms mode-stranded (both directions) | **OPEN** (`build.py:140-154` vs `:220-235`) |
| S4 | OAG literals scattered; no real-build unwrap assert in CI | **OPEN** (addressed via Item 1) |
| S5 | `get_type_hints` swallowed → body params demoted (P1b) | **OPEN** (`introspect.py:213-216`) |
| S6 | `_discover_resources` silent `[]` (P1c) | **OPEN** (`render.py:31-43`) |
| S7 | No stage-freshness guard (P2) | **OPEN** |
| S8 | `urlopen` no timeout | **OPEN** (`provision.py:40`) |
| S9 | Provenance version lie | **FIXED** (#38, `build.py:24-43`) |
| L1 | `union_members` write-only; `select_method_for_verb` unwired (A3/A4) | **OPEN** |
| L2 | `_ALL_SLUGS` hardcoded in test (B6) | **OPEN** (`test_sdk_build.py:30-43`) |
| L3 | D1–D5 decompositions + C901 gate (D6) | **OPEN** (none done; no mccabe in ruff select) |
| L4 | F1 classification primitive / F2–F5 | **PARTIAL** (F1: `normalize_operation_ids` federated-only) / **OPEN** |

## Appendix B — Stale `.agents/context` statements (docs-truth pass)

1. `index.md:42-50` — repo map omits `generator/opmodel/` (the shared base) entirely.
2. `index.md:53-55` — "generated SDK/CLI is disposable … never hand-edit" — false for CLIs: `main.py`/`hooks.py`/`custom/__init__.py` are the documented hand-owned seam; the wipe boundary is `_generated/`.
3. `index.md:39-40` — entry point is now `classify.build_ir` (federated detect + merge), not `build_cli_ir`.
4. `sdk-generator.md:210-212` — "the one remaining cli-shim edge inside sdk/ is sdk/docs.py" — `sdk/build.py:398` also imports `cli.classify` (added with federated live smoke).
5. `sdk-generator.md:358-360` — "phantasos needs none of the SDK's runtime deps" — true only for smoke; five nox sessions must pre-install `sdk_runtime_deps()` for the in-process stages; bare pip-install + `sdk build` of a facade product fails.
6. `scaffold.md:41,63` — gated-tests/whitespace-gate lists omit `test_federated_live.py.jinja` and its `federated` gate flag.
7. `phantasos-cli.md:42-43` — names the `cli/introspect.py` shim as the real path; actual path is `classify.build_ir` → `cli_operations` → `opmodel.introspect`.
8. `cli-generator.md:257-258` — app.py description predates lazy `_META` resolution; the doc is internally inconsistent with its own lazy-loading section.
