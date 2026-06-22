# Merge develop + rebase #30 docs onto the wrapper architecture — plan

> **For agentic workers:** execute task-by-task via subagent-driven-development. Steps use `- [ ]`.

**Goal:** Bring current `develop` (= #28 + **#30 generated-SDK-docs** + **#31 posture/PUT-update**)
into `feature/sdk-cleanup` so it merges back cleanly, **without regressing any wrapper-architecture
functionality**, and re-realize #30's docs feature on the new `client.<object>.<verb>` surface so
the doc enhancements land cleanly.

**HARD RULE — the wrapper architecture always wins.** Wherever #30/#31 assume the old raw-`*Api`
surface or the pre-refactor classifier, we adapt *them* to the wrapper, never weaken the wrapper.

**Inputs:** breaking-change analysis `docs/research/2026-06-20-develop-merge-breaking-changes.md`
(2× converged OCD reviews); #30 design `docs/specs/2026-06-17-sdk-generated-docs-design.md` (on
develop); the wrapper design `docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md`.

**Tech stack:** Python 3.12+, pydantic v2, Jinja2, OAG-wrapped SDK gen, MkDocs-Material +
mkdocstrings, `uv`+`nox`, pytest.

## Global Constraints
- Prefix every uv/nox command with `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-sdkcleanup`; for
  venv-backed sessions (`live`, `docs`) also `NOX_ENVDIR=/tmp/phantasos-nox`.
- Offline gate green after every task: `uv run nox -s gate`. The docs integration gate is
  `nox -s docs` (venv-backed; skips without prereqs).
- Wrapper invariants preserved (verify, don't assume): object-granular `client.<object>`, raw
  `*Api` hidden from the client, `_WRAPPERS`/`_bindings`, `update_*` PUT → `.replace`, the golden
  command-tree retained (regenerate only for spec-driven additions, never to hide a logic change).
- `develop`'s features preserved: posture product builds; PUT-update body-requiredness; the
  error-envelope diagnostics; the docs feature's intent (Diátaxis page set, tailored guides,
  mkdocstrings reference, strict build).
- No new SDK runtime deps. Frozen oracles (`.claude/harness.toml`) never edited.

## Approach (two phases)
- **Phase 1 (merge + blockers):** land the merge with wrapper-wins conflict resolution; close the
  3 blockers + golden. Outcome: merged branch builds prisma-browser **and** posture, gate green,
  all wrapper + non-docs develop features intact. Docs deliberately stay *off* on prisma-browser at
  the end of Phase 1 (we don't ship docs that teach the wrong surface) — re-enabled in Phase 2.
- **Phase 2 (docs rebase):** re-realize #30's docs on the wrapper surface, then re-enable
  prisma-browser's `docs:` and prove `mkdocs build --strict` with wrapper-correct content.

## Expert review outcome (2026-06-20)

Reviewed by an independent principal-engineer subagent (verified against the real code/build).
Verdict: **GO-WITH-CHANGES** (NO-GO as originally written). All required changes folded in above:
- **BLOCKER (B3) — fixed (P1.2).** The original "drop the `update_` prefix" silently regressed
  develop's PUT framework: `classify_name` is a dual consumer, and posture's only update is a PUT
  with no PATCH twin and no `cli.yml hide`, so its `update posture-check` command would vanish
  (latent — posture has no golden, not in any gate); and the gate would red on develop's 3
  auto-merged PUT tests in `test_cli_classify.py`. Fix = decouple: `opmodel.classify_name`→None for
  the SDK `.replace`; CLI-local `update_*`→put in `build_cli_ir`; re-add `"put"` to `SubVerb` +
  `_SUBVERB_PRIORITY` (the research's "runtime kept +put" claim was false).
- **Minor gaps — folded in:** remove the auto-merged `docs:` block in P1.1 (else docs ship ON
  teaching the raw surface); create posture's `sdk.yml operations:` block (P1.4); pin the `hide`
  early-continue before `_resolve_object` (P1.4); migrate `showcase_resource` plural→singular +
  rebase `showcase_variant` (P2.1/P2.5); spike the wrapper-reference `--strict` build + decide on
  docstring-less wrapper methods (P2.4).
- **Confirmed sound:** B1/B2/M4/M5 resolutions; the two-phase order; Phase 2's #30-intent fidelity
  (replacing the raw-prefix heuristic with the wrapper's clean verbs is a simplification, not a loss).

---

## Phase 1 — merge + blocker fixes

### Task P1.1 — Merge develop; resolve conflicts; neutralise the auto-merged `docs:` block
**Files:** the 6 conflicted (`classify.py`, `productconfig.py`, `products/prisma-browser/sdk.yml`,
`tests/test_render.py`, `.agents/context/sdk-generator.md`, `CHANGELOG.md`) **plus the auto-merged
`tests/test_cli_classify.py` and `products/{prisma-browser,posture}/sdk.yml docs:` blocks** (these
auto-merge into a state later tasks must reconcile — they are NOT in the conflict list but DO need
attention).
**Resolution (wrapper-wins):**
- `classify.py` — **keep OURS (the shim)**; `opmodel/classify.py::_VERB_PREFIXES` stays WITHOUT
  `("update_","update","put")` (the SDK wrapper needs `update_*`→None for `.replace`). The CLI's PUT
  classification is re-added *locally* in P1.2 (do NOT touch the shared map). Keep develop's
  PATCH-conditional body-requiredness post-pass in `build_cli_ir` (auto-merge takes it; confirm the
  feature branch's *unconditional* `if verb=="update": f.required=False` is GONE, not re-added).
- `productconfig.py` — keep BOTH `operations:` (ours) and `docs:` (develop) fields on `ProductConfig`.
- `prisma-browser/sdk.yml` — keep BOTH our `operations:` block and develop's `transforms`
  cloud-storage entries; **comment out / remove the auto-merged `docs:` block** (showcase_resource,
  showcase_variant, raw-surface `examples:`) — docs stay OFF until P2 (else Phase 1 ships docs that
  teach the raw surface). Posture: same — defer any `docs:` to P2.
- `tests/test_render.py` — keep BOTH sides' imports/helpers/tests.
- `tests/test_cli_classify.py` — auto-merge takes develop's PUT-asserting version
  (`test_classify_update_is_put`, `test_update_put_only_keeps_body_required`,
  `test_update_merged_patch_and_put...`). These REQUIRE `update_*`→put **for the CLI** — they MUST
  pass after P1.2 (do NOT delete them; deleting would silently bless a posture regression).
- context-doc + CHANGELOG — union (reconciled in Finalisation).
- [ ] Steps: `git merge develop`; resolve as above; `git diff --check`; commit. (Do NOT build/gate
  yet — B1/B2/B3 fixes land in P1.2–P1.4 first.)

### Task P1.2 — B3: decouple CLI PUT classification from the SDK wrapper (the hard fix)
**Why:** `classify_name` is a DUAL consumer. The SDK wrapper needs `update_*`→**None** (→ `.replace`,
`wrapper.py:249`, contract tests in `test_opmodel_classify.py`/`test_sdk_wrapper.py`). The CLI needs
`update_*`→**`(update,put)`** so a live `update` command exists — **posture's only update is a PUT**
(`UpdatePostureChecksByID`, no PATCH twin, no `cli.yml hide`), so without this its `update
posture-check` command vanishes (latent: posture has no golden + isn't in any gate session). Develop
solved this with one shared prefix; that's mutually exclusive with our `.replace`.
**Files:** `cli/classify.py::build_cli_ir`, `cli/ir.py` (`SubVerb`), `runtime.py.jinja`
(`_SUBVERB_PRIORITY`), tests `tests/test_cli_classify.py` (already present from the merge).
- [ ] **Keep `opmodel/classify.py::classify_name` returning None for `update_*`** (SDK `.replace`
  preserved; wrapper contract tests stay green).
- [ ] In `build_cli_ir` (the CLI layer ONLY): classify an `update_*` raw method as `(verb=update,
  sub_verb=put, object=<noun>)` via a CLI-local prefix check (mirror develop's intent), independent
  of the shared `classify_name`. This restores the `update posture-check` command + the PUT-vs-PATCH
  requiredness post-pass's input.
- [ ] **Re-add `"put"` to the `SubVerb` Literal in `cli/ir.py`** (our branch stripped it; develop had
  it) and **re-add `"put"` to `_SUBVERB_PRIORITY` in `runtime.py.jinja`** (our branch dropped it — the
  research's "runtime kept +put" claim was FALSE; verified absent). Without the priority entry,
  `_pick_binding`'s PATCH-vs-PUT ordering defaults the PUT binding to 99.
- [ ] Tests: develop's 3 PUT tests in `test_cli_classify.py` PASS; the wrapper contract tests in
  `test_opmodel_classify.py`/`test_sdk_wrapper.py` STILL PASS (`OBJECT_OF("update_*") is None`,
  `.replace` present); add a posture-specific assertion that `update posture-check` is a live command
  with required body. (Build posture CLI to confirm the command exists.)

### Task P1.3 — Complete the `cli/introspect.py` shim (BLOCKER 2)
**Files:** `src/phantasos/generator/cli/introspect.py`; a shim test.
- [ ] Re-export `_enum_values`, `_unwrap_optional` in the shim's imports + `__all__` (verified these
  are the only two relocated privates #30's `examples.py`/`docs.py` need; audit confirms no others).
- [ ] Test: `from phantasos.generator.cli.introspect import _enum_values, _unwrap_optional` resolves;
  each `is` the `opmodel.introspect` object.

### Task P1.4 — SDK-side op suppression: `OperationOverride.hide` (BLOCKER 1)
**Files:** `src/phantasos/config.py` (`OperationOverride`), `src/phantasos/generator/sdk/wrapper.py`,
`products/{prisma-browser,posture}/sdk.yml`, tests.
- [ ] Add `hide: bool = False` to `OperationOverride` (frozen, extra=forbid).
- [ ] In `build_wrapper_context`'s op loop: the `hide` early-`continue` MUST be placed **before
  `_clean_verb_and_method`/`_resolve_object`** (`wrapper.py:~610`, where `_resolve_object` raises
  synchronously at `wrapper.py:219`) — a hidden op is dropped (no wrapper method) and does NOT trip
  the anchorless gate. SDK analog of `cli.yml hide`.
- [ ] prisma-browser `sdk.yml operations:` — add `hide: true` rows for the 4 asset uploads + the
  cloud-storage PUT. **Posture `sdk.yml` has NO `operations:` block — CREATE one** with `hide: true`
  for `config_file_upload.initiate_config_upload`.
- [ ] Tests: a hidden op emits no wrapper method + doesn't trip the gate; build prisma-browser +
  posture succeed (real evidence in report).

### Task P1.5 — Regenerate the golden command-tree + Phase-1 gate (MINOR)
**Files:** `tests/golden/prisma-browser.tree.json`.
- [ ] Regenerate (legitimate changes are develop's spec-driven additions: +`cloud-storage-provider`
  commands, new flags). Confirm NO `update:*` leaks into the *prisma-browser* golden (prisma-browser
  hides its PUTs; posture has no golden), and no existing command/flag changed semantics; record the
  diff in the commit.
- [ ] Full gate green: build prisma-browser SDK+CLI, build posture SDK, `uv run nox -s gate`.

**Phase 1 exit:** merged branch builds both products + gate green; wrapper invariants intact;
**develop's PUT-update framework intact (posture `update posture-check` lives, SDK `.replace` lives)**;
error-envelope intact; both products' `docs:` left OFF (deferred to P2).

---

## Phase 2 — re-realize #30 docs on the wrapper surface

**#30 intent → wrapper mapping (the spine of Phase 2):** keep #30's Diátaxis page set (Home,
Getting-Started, Architecture, Guides {auth, pagination, CRUD}, mkdocstrings Reference), the
config-gated `docs:` mechanism, the strict-build `_hooks.py`, and the showcase-driven tailoring —
but drive them from the **wrapper** (`client.<object>.<clean_verb>`), and replace #30's raw-method
verb-classification heuristic with the wrapper's already-canonical clean verbs.

### Task P2.1 — `docs.py`: introspect the wrapper, not the raw `*Api`
**Files:** `src/phantasos/generator/sdk/docs.py`, `src/phantasos/config.py` (`DocsConfig`).
- [ ] `build_docs_context` introspects `_WRAPPERS` (object-granular) instead of the default
  `_RESOURCES`: use `cli_operations(cfg.package, project_dir)` (or `introspect(..., registry_attr=
  "_WRAPPERS")`) so the showcase is a wrapper OBJECT with CLEAN verbs.
- [ ] `DocsConfig.showcase_resource` semantics → a wrapper **object** attr (singular). Validate
  against `_WRAPPERS` keys (fail-fast with the available list). Keep `DocsOperations` as an optional
  override but it is rarely needed now (the wrapper already canonicalized create/get/list/update/
  delete).
- [ ] **Config-value migration (explicit step):** every product's `sdk.yml docs.showcase_resource`
  is currently a PLURAL raw `_RESOURCES` key (`applications`, `posture_checks`) — change each to the
  singular `_WRAPPERS` object key (`application`, `posture_check`). This is a config edit in each
  product, not just a code swap. Done in P2.5 when docs are re-enabled.
- [ ] Replace the raw-prefix verb heuristic (`classify_operations`/`_slot`/`_noun`/fewest-params/
  exclude-`bulk_`) with reading the object's clean methods + `_bindings`: the slots are the wrapper's
  `create`/`get`/`list`/`update`/`delete` directly; `has_*` flags from method presence; the request
  model + required fields from the wrapper method's `body` ParamView; the list `items_field`/envelope
  from the wrapper's `list` return. (`replace`/non-CRUD wrapper methods can extend the guide later;
  for the showcase, the 5 CRUD slots.)
- [ ] Test (real built SDK): `build_docs_context` for showcase `application` yields slots whose
  method names are the CLEAN verbs and whose call attr is the OBJECT.

### Task P2.2 — `examples.py`: synthesize wrapper calls
**Files:** `src/phantasos/generator/sdk/examples.py`.
- [ ] Keep the model-expression synthesizer (`synthesize_body`/`_model_expr`/`_value`) — it builds a
  pydantic constructor and is surface-independent. Change the CALL wrapping the docs emit to the
  wrapper: `client.<object>.create(body=<Model(...)>)`, `.get(id=...)`, `.list(<filters>)`,
  `.update(id=..., body=<Model(...)>)`, `.delete(id=...)`. For oneOf/variant create, show the
  wrapper accepting the wrapper-model body (per the wrapper's `body_wrapper`).
- [ ] Confirm the `_enum_values`/`_unwrap_optional` import resolves (P1.2) — or repoint to `opmodel`.

### Task P2.3 — Rewrite the guide/explanation templates to the wrapper surface
**Files:** `src/phantasos/scaffold/docs/{getting-started,architecture}.md.jinja`,
`docs/guides/{crud,pagination,authentication}.md.jinja`, `docs/index.md.jinja`.
- [ ] `crud.md` — `client.<object>.create/get/update/delete(...)` (clean verbs, `body=`/`id=`), only
  the slots that exist (partial-CRUD preserved).
- [ ] `pagination.md` — the wrapper's built-in pagination: `for item in
  client.<object>.list(all_pages=True).data:` (NOT `client.paginate(client.<res>.<raw_list>)`).
  Gated on `has_pagination and showcase.has_list`.
- [ ] `getting-started.md` — `Client.from_env()` (unchanged) then the first real call as
  `client.<object>.list(...)` / `.get(id=...)`.
- [ ] `architecture.md` — rewrite the prose + Mermaid for the wrapper model: `client.<object>` typed
  wrappers over a shared api client, the op-model, `list(all_pages=)`, raw `*Api` as an internal
  detail. Drive component mentions from `has_*` (unchanged).
- [ ] `authentication.md` — unchanged (credential-driven, surface-independent); verify.

### Task P2.4 — API Reference: foreground the wrapper (spike `--strict` FIRST)
**Files:** `src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja`, `scaffold/mkdocs.yml.jinja`.
**Risk: MEDIUM until spiked** (the griffe path over non-pydantic wrapper classes is unproven).
- [ ] **Spike before committing:** add `extras/resources.py` to the reference walk in a throwaway
  build of the real prisma-browser SDK and run `mkdocs build --strict`; capture the warning log.
  Cross-refs are likely fine (#30's config sets `show_signature_annotations`/`signature_crossrefs`
  false and every model type already has a page), but confirm empirically. If `--strict` breaks,
  fold the needed mkdocstrings option/filter change into this task before proceeding.
- [ ] Decision (wrapper-wins): the user-facing operation surface is `extras/resources.py`. Walk
  **`extras/resources.py` SPECIFICALLY** (the `<Object>Resource` classes) + `models/` — NOT a glob
  of `extras/` (that would pull in `facade`/`auth`/`pagination`, which #30 decision #8 excludes).
  Wrapper internals (`_bindings`/`_serialize`/`_to_raw`/`_select`) are already hidden by the existing
  `!^_` filter — confirm. Keep the `_hooks.py` duplicate-param filter + mkdocstrings options.
- [ ] **DECIDED (user): emit a short per-method docstring in the wrapper generator.** Thread the
  op `summary` (from `OperationInfo.summary`, already in the op-model) into `MethodView` in
  `build_wrapper_context`, and emit it as the method docstring in `resource.py.jinja` (a one-line
  summary; for multi-binding `.get`/`.list` use the object+verb, e.g. "Get a device group."). This
  changes the emitted `extras/resources.py` for ALL products (a strict improvement) — update the
  `test_render.py`/`test_sdk_wrapper.py` assertions that inspect the emitted source accordingly. The
  reference then renders documented wrapper methods, not bare signatures.

### Task P2.5 — Rewrite the product `docs:` blocks (examples + showcase) + re-enable docs
**Files:** `products/prisma-browser/sdk.yml`, `products/posture/sdk.yml`.
- [ ] Rewrite each hand-authored `docs.examples.<slot>` verbatim override from the raw API to the
  wrapper surface (`client.application.create(...)`, `client.posture_check.create(...)`, …).
- [ ] Migrate `docs.showcase_resource` from the plural raw key to the singular wrapper-object key
  (`applications`→`application`; `posture_checks`→`posture_check`), and rebase `docs.showcase_variant`
  (added by #30) onto the wrapper's variant handling.
- [ ] Re-enable the `docs:` block for prisma-browser (removed/commented in P1.1), now wrapper-correct;
  set posture's showcase if it opts in. This is the step that turns docs back ON.

### Task P2.6 — Update the docs tests + gate to the wrapper surface
**Files:** `tests/test_sdk_docs_emitted.py` (+ any docs-render tests), `noxfile.py` (`docs` session).
- [ ] Rewrite the assertions that currently lock in `client.<resource>.<raw_method>` to assert the
  wrapper surface (`client.<object>.<clean_verb>`, `body=`, `list(all_pages=)`), partial-CRUD, the
  credential env vars, and "no docs when `docs:` absent". Treat as recorded oracle changes.
- [ ] Add a dispatch-style assertion that the emitted CRUD examples reference REAL wrapper methods
  (cross-check against `_WRAPPERS[object]`'s methods) so a future raw-surface regression fails.

### Task P2.7 — Verify the full docs pipeline on the wrapper
- [ ] Build prisma-browser with `docs:` → run the real scoped introspect → render → `nox -s docs`
  (`mkdocs build --strict`) succeeds; grep the emitted `docs/` for the wrapper surface and assert
  **no** `client.applications.`/`.list_applications(`/`client.paginate(` raw patterns remain.
- [ ] Full `nox -s gate` green; `nox -s context -- --check` clean (update
  `.agents/context/sdk-generator.md` narrative for the wrapper-driven docs stage).

---

## Finalisation
- [ ] Reconcile `CHANGELOG.md [Unreleased]` (both feature sets, one coherent section) +
  `.agents/context/{sdk-generator,cli-generator,components,product-config}.md` narratives; `nox -s context`.
- [ ] Confirm: prisma-browser + posture build; CLI dispatches the wrapper; docs teach the wrapper +
  `mkdocs --strict` green; golden retained; gate green. Then the branch is ready for the
  `feature/sdk-cleanup → develop` PR.

## Self-Review (post expert review)
- **Findings coverage:** B1→P1.4; B2→P1.3; **B3→P1.2 (decouple CLI/SDK PUT classification)**;
  M4→P2.1–P2.7; M5→P1.5.
- **#30 intent coverage:** Diátaxis page set + showcase + reference + strict hook + config-gating all
  retained (P2.1–P2.7), retargeted to the wrapper; the raw-prefix heuristic is *replaced* by the
  wrapper's canonical verbs (simplification, not loss).
- **Wrapper-wins:** every conflict resolved toward the wrapper, with **both halves of the wrapper
  preserved** (SDK `.replace` AND the CLI `update` command) and develop's PUT framework intact. No
  wrapper invariant weakened.
- **Decisions to confirm with the user before build:**
  1. **P2.4 reference:** autodoc the wrapper (`extras/resources.py`) + models, raw `api/` internal
     (recommended) — vs. keep #30's `api`+`models` breadth.
  2. **P2.4 docstrings:** emit a short per-method docstring from the op summary in the wrapper
     generator (recommended, richer reference) — vs. ship signature-only now + a follow-up.
</content>
