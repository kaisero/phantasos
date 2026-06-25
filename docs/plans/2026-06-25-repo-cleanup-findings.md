# Repo cleanup — code-quality findings (phantasos)

- **Date:** 2026-06-25
- **Branch:** `feature/repo-cleanup`
- **Status:** Findings report — **no code changes made**. This is the precursor to an implementation plan; nothing here is actioned until reviewed.
- **Method:** three read-only analyst sub-agents run in parallel, each invoking `python-pro`, each with a distinct lens and full tooling (radon/xenon/ruff C901, vulture/deadcode, pip-audit, a fresh `pytest` + coverage run). Findings below are de-duplicated and ranked across all three.
- **Scope:** `src/phantasos/**`, `tests/**`, and scaffold/Jinja templates (flag-only). **Excluded:** `products/`, `tools/`.
- **Guardrails honored:** the `generator/sdk` ↔ `generator/cli` logic duplication is **deliberate separation-of-duty** and was treated as off-limits; frozen oracles in `.claude/harness.toml` were never recommended for edits.

---

## 1. Executive summary

**The codebase is in good health.** Evidence, not vibes:

- **Tests:** 567 passed, **0 failed**, **0 skipped** (real SDK sibling present), **95.84%** coverage on a fresh run. **No mocking of the system-under-test or the prisma-browser API boundary** — the repo's test policy is genuinely honored.
- **Dependencies:** every runtime dep (`ruamel.yaml`, `jinja2`, `pydantic`, `jmespath`, `typer`) is load-bearing; **no unused deps**; `pip-audit` reports **no known vulnerabilities**; **no dead Jinja templates**.
- **Complexity:** every module scores maintainability-index rank **A**. The debt is **localized, not systemic** — essentially two god-functions carry it.

So this is not a rescue job. The wins are **surgical**: a handful of proven dead-code removals, one clearly-accidental duplication that two independent agents flagged, two over-complex functions, one layering inversion, and a test suite whose *content* is excellent but whose *file organization* has drifted.

**The three highest-value moves:**
1. **`on_sys_path()` context manager** — kills a byte-identical `sys.path` guard copy-pasted across 3 source modules. Flagged independently by **two** agents. Cheapest high-value win in the repo.
2. **Split `test_cli_emitted.py`** (3,935 LOC / 152 tests / 0 parametrize) along its 6 natural behavioral seams — the single biggest structural debt.
3. **Decompose `build_cli_ir`** (`classify.py`, cyclomatic complexity **53**, the only F-rank function) into named pipeline stages.

**Net direction:** delete a little, extract a few seams, reorganize the tests. Resist the temptation to "modernize" (`match`/`StrEnum`) or DRY across the sdk/cli boundary — see §6 for what *not* to do.

---

## 2. Cross-agent consensus (highest confidence)

These were surfaced by more than one agent, or corroborated by independent tooling — treat them as the most trustworthy:

| Finding | Agents | Verdict |
|---|---|---|
| `sys.path` insert/try/finally/remove guard duplicated across `opmodel/introspect`, `cli/classify`, `cli/modelschema` (4th copy in `sdk/docs`) | Architecture **+** Deps/Dup | Extract `on_sys_path()` in `opmodel/` (shared base — no separation violation) |
| Layering oddity: `opmodel` (base) imports up into `cli.ir`; `sdk` reaches `opmodel` *through* the `cli/introspect` shim | Architecture (strong) **+** Deps/Dup (noted) | Move the pure vocab/primitives down into `opmodel` |
| Test render/import/cleanup boilerplate duplicated (~40 inline copies + 3 fixtures) and global-state (`sys.path`/`sys.modules`/config cache) mutation creates latent order-dependence | Tests **+** (mirrors the src `sys.path` finding) | One shared `render_and_import` fixture in `conftest.py` |
| Healthy baseline: no unused deps, no vulns, no dead templates, no SUT mocking, MI rank A everywhere | all three | Confirms "surgical, not structural" |

---

## 3. Prioritized backlog

Ranked by **(impact × confidence) / risk**. Effort: S/M/L. Risk: chance a change breaks behavior or a frozen contract.

### Tier 1 — Quick, safe, proven (do first)

| # | Item | Location | Impact | Conf | Effort | Risk |
|---|---|---|---|---|---|---|
| 1 | **`on_sys_path()` context manager** — replace the 3× byte-identical `sys.path` guard | `opmodel/introspect.py:199`, `cli/classify.py:131`, `cli/modelschema.py:169` (+`sdk/docs.py:173`) | High | High | S | Low |
| 2 | **Delete vestigial `OperationInfo.return_type`** — never set, never read; superseded by `return_model` | `opmodel/inventory.py:51` | Med | High | S | Low |
| 3 | **Delete 3 unused aliases** `_scalar_type` / `_field_kind` / `_union_members` (0 refs anywhere) | `opmodel/introspect.py:292-294` | Low | High | S | Low |
| 4 | **Dedup host CLI**: `_load_or_exit(product)` + `_build_ir_or_exit(loaded)` collapse a 3× guard and a 2× IR-build block; standardize error wording | `cli.py:34-41/76-95/116-132` | Med | High | S | Low |
| 5 | **Rename `test_cli_docs.py` → `test_sdk_docs_context.py`** (it imports & tests `sdk.docs`, not CLI docs) | `tests/test_cli_docs.py:20` | Med | High | S | Low |
| 6 | **Mark `test_build_emits_wrapper` slow** (17.2s OAG-jar build inside the unit suite) — move to `smoke`/a `slow` marker | `tests/test_sdk_build.py:33` | Med | High | S | Low |

### Tier 2 — Structural (real value, more care)

| # | Item | Location | Impact | Conf | Effort | Risk |
|---|---|---|---|---|---|---|
| 7 | **Split `test_cli_emitted.py`** (3,935 LOC) into ~6 files by seam: `environments`, `config`, `runtime`, `history`, `logging`, `output`; share fixtures via `conftest` | `tests/test_cli_emitted.py` | High | High | L | Med |
| 8 | **Consolidate emit fixtures + ~40 inline render/import/cleanup copies** into one `render_and_import` fixture; always clear the config cache there | `tests/conftest.py`, `test_cli_emitted*.py`, `test_cli_dispatch_matrix.py` | High | High | M | Low |
| 9 | **Decompose `build_cli_ir`** (CC 53/F) into named stages (`_validate_defaults`, `_emit_commands`, `_relax_patch_bodies`, `_flag_get_by_id_only`, `_resolve_columns`); promote the 67-line `_emit` closure to a module-level fn | `cli/classify.py:395-611` | High | High | M | Med |
| 10 | **Data-drive `render_cli`** (CC 32/E): replace ~14 literal `render(...)` calls with a table; extract `_enrich_ir` and `_render_docs` | `cli/render_cli.py:295-464` | High | High | M | Med |
| 11 | **Fix the layering inversion**: move `Verb`/`SubVerb`/`FlagKind` (pure `Literal` vocab) down into `opmodel` (e.g. `opmodel/vocab.py`), re-export from `cli.ir` for compat; relocate `_unwrap_optional`/`_enum_values` to their real home in `opmodel/introspect` | `opmodel/classify.py:12`, `opmodel/introspect.py:17`, `cli/introspect.py` shim | Med | High | M | Med |
| 12 | **Close the worst coverage gaps**: add `test_sdk_preprocess.py` (module at 84% — `_resolve_type` allOf/cycle, mojibake repair, `hoist_items`); add a `cli.py` error-funnel test (80% — the `except Exception` exit-code path) | `sdk/preprocess.py`, `cli.py:183-194` | Med | High | M | Low |
| 13 | **Trim `emitted_real`** to spec-dependent cases only (drop lint-clean/version/config-init duplicates of fakesdk); **parametrize** copy-pasted families (`env_delete_*`, diagnostics, table-rendering) | `tests/test_cli_emitted_real.py`, `test_cli_emitted.py` | Med | Med | M | Low |

### Tier 3 — Lower value / cautious / deferred

| # | Item | Location | Notes |
|---|---|---|---|
| 14 | **Type `LoadedProduct` component slots** with `Protocol`s, replacing `Any | None` + `hasattr(...)` duck-typing | `productconfig.py:161-172`, `render_cli.py:334` | Med risk (touches load path); pairs with #11 |
| 15 | **Error-template Jinja base** with `{% block extract %}` — `nested_error.py.jinja` & `list_error.py.jinja` are ~40/55 lines identical | `sdk/components/errors/*.jinja` | **Template/emitted scope — flag-only.** Maintainability-only (one vendored per SDK). Changing templates changes generated output. |
| 16 | **Resolve `tests/cli/` split axis** — de-dup `modelschema` (tested in two places), relocate `test_flags.py`; make `tests/cli/` mean exactly "the CLI-docs feature" *or* move all `test_cli_*` into it | `tests/test_cli_modelschema.py` ↔ `tests/cli/test_modelschema.py` | Pick one axis; pairs with #5/#7 |
| 17 | **`emitted` fixture scope** — module/session-scoped render (with per-test HOME/env isolation) to cut repeated re-render cost | `tests/test_cli_emitted.py:33` | Lower priority; depends on #8 |
| 18 | **Optional honesty bumps** — host `pydantic>=2` → `>=2.11` (true effective floor); decide fate of reserved `select_method_for_verb` ("phase2" placeholder) | `pyproject.toml:23`, `cli/classify.py:170` | Maintainer's call |
| 19 | **Informational** — `tests/fixtures/fakesdk/**` and `tests/golden/**` are oracles but **not** in `protected_globs`; consider adding them (note: `harness.toml` is itself frozen — human edit only) | `.claude/harness.toml` | Do not edit; surface for human decision |

---

## 4. Detailed findings by theme

### 4.1 Dependencies — *no removals warranted*
- **`jmespath`** — load-bearing in exactly one runtime file (`cli/columns.py`): `jmespath.compile(path).parsed` + AST walk to validate `cli.yml` column paths against the model. Re-implementing in stdlib is more code/risk than the dep. **Keep.**
- **`ruamel.yaml` (runtime) vs `pyyaml` (test-only)** — no overlap in `src`: ruamel does round-trip spec rewriting (`preserve_quotes`, custom width/indent); pyyaml only `safe_load`s emitted `mkdocs.yml` in 4 test files. **Keep both — intentional.**
- **`typer`** — structural to both the host CLI and every emitted CLI; the tight `>=0.26.7` floor is documented (`standalone_mode=False` exit-code behavior verified against typer 0.26.7 / click 8.4.1). **Keep.**
- **`pydantic>=2`** — true effective floor is **2.11** (the build-time facade introspection imports the generated SDK, which needs 2.11). Low-risk honesty bump available (#18).

### 4.2 Dead code — *small and proven*
- `OperationInfo.return_type` (`inventory.py:51`) — declared once, set/read **never** (8 construction sites omit it); superseded by `return_model`/`items_field`/`response_fields`. **Remove (#2).**
- `_scalar_type` / `_field_kind` / `_union_members` (`introspect.py:292-294`) — 3 of 5 back-compat aliases with **zero** references in src/tests/templates (only `_enum_values`/`_unwrap_optional` are actually re-imported). **Remove (#3).**
- `select_method_for_verb` (`classify.py:170`) — in `__all__` but unwired; its own comment says `TODO(phase2)`. Deliberate placeholder, not a bug — maintainer's call (#18).
- **Tooling note:** `vulture --min-confidence 90` on `src/` reported nothing. `deadcode` is broken on Python 3.14 (`ast.Str` removed). The `.coverage` at repo root had no readable data for one agent; the authoritative coverage numbers come from the **fresh** run (§1, 95.84%). Vulture's lower-confidence hits were all verified as **live dynamic dispatch** (Jinja context fields, Typer commands, pydantic validators, `noxfile` consumers) — recorded so they aren't re-flagged.

### 4.3 Intra-repo duplication (within-path only)
- **`sys.path` guard ×3-4** — the headline (#1). Byte-identical; canonical home is `opmodel/` which both `cli` call sites already depend on, so a shared helper does **not** cross the sdk/cli boundary.
- **Host `cli.py`** — `load_product`+exit guard ×3 and the IR-build sequence ×2 (`cli_discover` vs `cli_build`, differing only in comments). Two small helpers fix both (#4).
- **Error templates** — `nested_error`/`list_error` ~40/55 identical lines; a Jinja base block would fix it, but it's template/emitted scope and maintainability-only (#15).
- **Deliberately NOT flagged:** `cli/examples.py` vs `sdk/examples.py`, the two `_command_view`s, parallel classify logic, the `_CLI_VERB_PREFIXES` vs `_VERB_PREFIXES` `update_` divergence — all intentional separation-of-duty / contract-guarded.

### 4.4 Architecture & complexity
- **`build_cli_ir`** (`classify.py:395`) — CC **53**, the repo's only F-rank function: index-building + default validation + a 67-line `_emit` closure + the classify loop + five post-processing passes, all in one body. Extract-function/pipeline refactor (#9). *Not* a `match`/dispatch problem — the classification ladder itself is already clean.
- **`render_cli`** (`render_cli.py:295`) — CC **32/E**: path-safety + IR enrichment + ~14 literal render calls + conditional doc emission. Data-drive + extract (#10).
- **Layering inversion** — base `opmodel` imports up into `cli.ir`; `sdk` borrows introspection primitives *through* the `cli/introspect` shim. Move vocab/primitives down to restore acyclic `opmodel → {sdk, cli}` (#11).
- **`LoadedProduct`** — five `Any | None` component slots drive `hasattr(...)` runtime checks; `Protocol` typing would restore structure (#14).
- **Other C-rank functions** (`load_product`, `build`, `_introspect`, `_build_method`, `collapse_allof`) are sequential orchestrators — breadth, not tangled nesting. Low priority; leave unless touched.

### 4.5 Tests & coverage
- **Content is strong; organization has drifted.** Central debt: `test_cli_emitted.py` at 3,935 LOC / 152 tests / **0 parametrize** (#7), the misnamed `test_cli_docs.py` (tests `sdk.docs`) (#5), and an unprincipled `tests/cli/` split that duplicates `modelschema` coverage (#16).
- **Duplication & runtime:** ~40 inline render/import/cleanup copies (#8); pure-generator behaviors (lint-clean, `--version`, `config init/show`) re-asserted on both fakesdk *and* the real SDK for little marginal signal (#13); the 17s OAG-jar build sitting in the unit suite (#6).
- **Coverage distribution** is the real issue, not the headline number: heavy SDK-build modules (`preprocess.py` 84%, `provision.py` 90%) are tested only through one slow integration test, while the CLI surface is over-tested (#12).
- **Policy clean:** no SUT/boundary mocking. One orchestration test (`test_build_runs_transforms_then_hook`) mocks 5 collaborators to assert *sequencing* — acceptable, but don't grow assertions on the mocked internals.

---

## 5. Suggested sequencing (if/when we act)

1. **Batch A — Tier 1 (one small PR).** Items 1–6: pure deletions, one context manager, two helper extractions, two test renames/markers. Each is independently reversible and behavior-preserving; run `nox -s gate` + `nox -s tests` after.
2. **Batch B — test reorg (one PR).** Items 7, 8, 13, 16: split the giant file, consolidate fixtures, trim/parametrize. No `src` changes → low blast radius.
3. **Batch C — src complexity (one PR per function).** Items 9 then 10 — each is a self-contained function decomposition guarded by existing tests; keep them separate so review and bisection stay clean.
4. **Batch D — layering + typing (one PR).** Items 11 + 14 together (they touch the same types). Re-export for back-compat to avoid a churny import sweep.
5. **Coverage (fold into the above).** Item 12 lands naturally alongside Batch C/D.
6. **Defer / human decision.** Items 15 (template scope), 18, 19.

Every batch is small, evidence-backed, and respects the branch/release workflow (feature → `develop`, squash, `## [Unreleased]`).

---

## 6. What we deliberately will **not** do (anti-scope)

Recorded so a future pass doesn't "discover" these and undo deliberate decisions:

- **Do not DRY across `sdk` ↔ `cli`.** The duplication there is deliberate separation-of-duty. All extraction recommendations above are strictly within a single path or in the shared `opmodel` base.
- **Do not convert the prefix-loop classifiers to `match`.** They are already correctly data-driven (`for prefix, verb, sub_verb in _VERB_PREFIXES`); `str.startswith` has no clean `match` form.
- **Do not `StrEnum`-ify `Verb`/`SubVerb`/`FlagKind` as a drive-by.** These serialize verbatim into the emitted `ir.json` and `spec.py` — a frozen contract. If desired, do it inside the in-flight CLI IR-deepening work, not here.
- **Do not remove `ruamel.yaml` or `pyyaml`.** Different layers, no overlap in `src`.
- **Do not touch frozen oracles** (`.claude/harness.toml` `protected_globs`) — including `harness.toml` itself. Item 19 is a *suggestion for a human*, not an action.
- **Do not change scaffold/Jinja templates casually** — they're emitted into every generated SDK/CLI and guarded by defaults-sync / golden tests. Item 15 is flag-only.

---

## 7. Appendix — raw agent reports

The three sub-agent reports verbatim, for traceability. The synthesis above de-duplicates and re-ranks them; where they overlap (esp. the `sys.path` guard and layering), that overlap raised confidence.

### Appendix A — Dependencies, dead code, duplication

> Headline: no unused external deps, `pip-audit` clean, no dead Jinja templates. Proven dead: `OperationInfo.return_type` and 3 unused aliases. Accidental duplication: the `sys.path` guard (×3-4) and host `cli.py` guard/IR-build blocks. Error templates share ~40/55 lines.

Top 5 picks: (1) `on_sys_path()` context manager; (2) delete `OperationInfo.return_type`; (3) drop 3 unused aliases; (4) dedup `cli.py` with `_load_or_exit`/`_build_ir_or_exit`; (5) error-template Jinja base block. Cross-cutting note: codebase is lean — wins are small surgical removals/extractions, not structural.

### Appendix B — Test structure & coverage

> Suite health: 567 passed, 95.84% coverage, no SUT/boundary mocking. Lowest modules: `cli.py` 80%, `sdk/preprocess.py` 84%, `provision.py` 90%. Slowest: `test_build_emits_wrapper` 17.2s.

Top 5 picks: (1) split `test_cli_emitted.py` by seam; (2) resolve `tests/cli/` split + rename `test_cli_docs.py`→`test_sdk_docs_context.py`; (3) consolidate the 3 emit fixtures + ~40 inline copies into `render_and_import`; (4) mark the 17s build slow + add `test_sdk_preprocess.py`; (5) trim `emitted_real` to spec-dependent cases + parametrize copy-pasted families.

### Appendix C — Architecture & code smells

> Complexity is localized: `build_cli_ir` (CC 53/F) and `render_cli` (CC 32/E) carry it; every module MI rank A. Layering inversion: `opmodel` imports up into `cli.ir`. Cheapest win: the `sys.path` context manager.

Top 5 picks: (1) decompose `build_cli_ir` into named stages + promote `_emit`; (2) `sdk_on_path()` context manager; (3) data-drive `render_cli` + extract `_enrich_ir`/`_render_docs`; (4) fix the layering inversion (move vocab/primitives down to `opmodel`); (5) type `LoadedProduct` slots with `Protocol`s. Note: `match`/`StrEnum` deliberately down-weighted (current loops idiomatic; IR types cross a frozen contract).
