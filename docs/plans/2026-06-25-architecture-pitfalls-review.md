# phantasos — architecture review: the 5 most pressing pitfalls

- **Date:** 2026-06-25
- **Branch:** `feature/repo-cleanup`
- **Status:** Findings report — **no code changes made**. Read-only architecture review to *harden and simplify* the existing design.
- **Method:** four read-only reviewers run in parallel (SDK pipeline / CLI generator + IR / config layer / cross-cutting + harness), each with the relevant `.agents/context/` deep-dive plus first-hand code reading. Headline claims re-verified by the synthesizer against the source. Findings de-duplicated and ranked across all four.
- **Relationship to the cleanup report:** complements `docs/plans/2026-06-25-repo-cleanup-findings.md`. That one is a *code-quality* backlog (dead code, duplication, function complexity, test reorg — Tier-1 already landing). This one is *architecture-level*: systemic seams, contracts, and enforcement. No overlap except the layering inversion, noted where it recurs.
- **Update 2026-06-25:** added **Part II** — the five pitfalls validated empirically against the three incoming specs (adem / ngts / incidents) by three parallel spec-fingerprint reviewers. Answers "do the pitfalls still hold, and does the variety widen scope?" Short answer: **scope increases**, concentrated in the classification/mapping model and the reflection boundary.

---

## 0. Verdict

The architecture is **sound and well-layered.** `cli.py` is a thin dispatcher with no build logic; `productconfig.load_product` is a single clean loader; the SDK pipeline is cleanly staged; provisioning (checksum + atomic replace + traversal-guarded extraction), the smoke isolation, the preprocess transforms, `release.yml`, and the post-loop IR-resolution passes are genuinely solid — leave them alone.

The pressing risks are **not** structural rot. They are one recurring **failure-mode** choice and the seams that embody it:

> **Across both build stages, when an upstream assumption drifts — OAG's exact output, the reflected SDK shape, the spec's auth declaration, a hand-maintained mirror list — the generator degrades to a *silently-wrong artifact* with a *green build*, instead of failing loud.** The success signal (build exits 0 / smoke imports / gate passes) does not certify correctness, and the safety net that's supposed to make it real has structural holes.

Five pitfalls, ranked by severity × probability. Each is genuinely architectural (a seam, a contract, or an enforcement gap), not a code nit.

**(Part II caveat, added after spec validation):** the five below were derived from the two *enrolled, CRUD-shaped* products (prisma-browser / posture). Validated against the three *incoming* specs (adem / ngts / incidents), the picture widens: the dominant blocker is no longer "silent wrongness on drift" but a **classification/mapping model that assumes verb-first English CRUD operationIds and discards spec structure at the reflection boundary** — for ngts that's a *hard SDK build failure*, for adem an *empty CLI*. See **Part II** for the cross-spec evidence and five flexibility-model gaps (F1–F5) the variety reveals.

---

## Pitfall 1 — Brittle codegen/reflection seams fail *silently* on drift (no correctness floor) `HARDEN` — top

**What.** Both stages couple to a fragile upstream shape and *swallow* the mismatch, so a drifted assumption produces a valid-but-wrong artifact while the build stays green. Four independent instances, same root:

| # | Seam | Silent failure | Evidence |
|---|---|---|---|
| a | OAG codegen patches | anchor missing → `continue`, patch no-ops, returns 0 | `sdk/patches.py:166,192` (`# anchor absent (OAG changed) — skip`), counts captured but never asserted: `sdk/build.py:71,119` |
| b | CLI hint resolution | `get_type_hints` throws → `hints={}` → falls back to raw *string* annotation → `issubclass(str, BaseModel)` is False → **every body param demoted to path/query** | `opmodel/introspect.py:213-216,227,232` |
| c | Facade discovery | `__init__.py` regex matches nothing → `[]` → empty facade, no wrappers | `sdk/render.py:15,33-43` (called 3× per build) |
| d | List-envelope detection | hardcoded to `data`/`page_info`; a `items`/`results` envelope is read as the item itself → wrong table columns, no knob | `opmodel/introspect.py:180` |

**Why it's architectural.** The generator's entire value is producing a *correct* SDK/CLI. These seams convert "upstream changed" (OAG upgrade, a new spec shape, a `from __future__ import annotations` module) from a loud failure into a subtly broken shipped artifact — the worst failure class for a code generator, surfacing at the *consumer's* runtime far from the build. The memory log already records two of these as real production bugs ("oneOf wrapper output leak", enum 401s).

**The net can't catch it.** `smoke` only proves modules *import* (syntax), not behavior (`sdk/smoke.py`). The patch *tests* use hand-written fixtures (`_INNER_SRC`/`_WRAPPER_SRC` in `tests/test_sdk_patches.py`) that re-encode the assumed OAG shape — so on an OAG bump the patch and its fixture drift *together* and the offline gate stays green. (See Pitfall 5.)

**Harden.** Make each seam distinguish *"no candidates"* (fine) from *"candidates present, anchor/shape gone"* (drift → fail loud):
- Patches: return `(patched, skipped_marker_present)`; `apply_generic_patches` raises if any marker-bearing file went unpatched. Assert patch-count floors on the real-build path (`live`/`smoke`, which already build prisma-browser).
- Hints (b): do **not** swallow into `{}` — let `get_type_hints` failures fail the build (or at minimum count + log per method); a generator must never guess a param's location from a string.
- Facade (c): assert `_discover_resources` is non-empty when `api/__init__.py` is non-trivial (and parse with `ast`, not regex — robust to formatting; compute once, not 3×).
- Envelope (d): add a per-op `cli.yml` `items_field:` escape hatch (do it the next time a non-conforming spec lands, not speculatively).

**Effort:** (a) ~½ day, (b) small + the most urgent, (c) ~2h, (d) defer until needed.

---

## Pitfall 2 — The stage-1→stage-2 boundary is in-process import + reflection: env-coupled, staleness-blind, isolation-inconsistent `HARDEN`

**What.** Stage 2 (and the SDK's own vendor step) import the *built artifact* into the generator interpreter and reflect over it (`importlib` + `inspect.getmembers` + `typing.get_type_hints`). Three compounding consequences:

- **Environment coupling.** The generator process must contain the *product SDK's* runtime deps (pydantic 2.11, urllib3, dateutil…) or the build crashes. The tell: `noxfile.py` pre-installs `sdk_runtime_deps()` in four sessions (`:234-235, 253-256, 296-297, 350-351`), each with a 3-5 line apologetic comment repeating the same root cause.
- **`sys.modules` surgery + path leak.** `render.py:143,147-162` (`_invalidate_pkg_modules`) manually deletes module entries so a re-import re-reads the pass-2 facade; `on_sys_path` deliberately does not remove an entry it didn't add (`opmodel/_pathutil.py:24-26`). Multi-build / rebuild correctness depends on this being exactly right.
- **No freshness check.** `cli build`/`discover` introspect whatever SDK is on disk with **no** comparison to the current spec/`sdk.yml`. Edit the spec, run `cli build` without rebuilding the SDK → a CLI for the *old* operation surface, exit 0. CI hides it (it always `sdk build`s immediately before); only real users hit it. `cli.py:32-48` → `classify.py:131-132`.

Note there are already **two** isolation strategies for the same "inspect built SDK" need: `smoke` uses a clean subprocess with its own venv (correct, well-reasoned); vendor/introspect do it in-process (fragile).

**Why it's architectural.** This is the spine connecting the two stages, and it's the single most complex, most environment-fragile seam in the system. The freshness gap is a real "mis-reports success" path.

**Harden.**
- **Cheap, now:** in `_build_ir_or_exit`, read the built SDK's `_about.py` `SPEC_VERSION` and compare to `loaded.context["spec_version"]` (already parsed); warn or `Exit(2)` on mismatch. Also catch `AttributeError`/`ModuleNotFoundError` from the reflection (`getattr(facade, registry_attr)` has no default — `introspect.py:207`) and convert to a clean "rebuild your SDK" exit instead of a raw traceback.
- **Longer-term:** move wrapper/docs introspection to the subprocess-emits-JSON pattern `smoke` already proves. One move deletes `_invalidate_pkg_modules`, the host-env dep coupling, *and* the `on_sys_path` leak.

**Effort:** freshness guard ~low; subprocess migration ~1-2 days.

---

## Pitfall 3 — Declaring `auth:` does not guarantee an authenticating SDK — silent production 401 `HARDEN`

**What.** `auth: scm_oauth` only wires a `TokenManager` that *fetches* a token. Whether the client actually *sends* `Authorization: Bearer` is decided entirely by the spec carrying `components.securitySchemes` + a `security` requirement (OAG emits the header-attaching code only then). `load_product` resolves the auth component **unconditionally** (`productconfig.py:214`) and reads the spec right there (`:236`) but only pulls `info` — it never inspects `securitySchemes`.

**Evidence it has already bitten.** `products/posture/hooks.py:_inject_security` is a per-product manual workaround whose own docstring says: *"The vendor spec declares NO securitySchemes/security, so OAG would generate methods that never send Authorization — every call 401s even with a valid token."* posture had no schemes; adem/prisma-browser do. The only guard against shipping a non-authing SDK is "the author remembered to write `hooks.py`."

**Why it's architectural.** A trust-boundary coupling (auth config ↔ spec) that is never validated, fails at *runtime in production* (401), and is one forgotten hook away on every new authed product. This is a concrete, highest-probability instance of Pitfall 1's class — elevated to its own slot because the blast radius is security and the fix lives at a different layer (config load).

**Harden.** When `cfg.auth` is set, assert the resolved spec has `securitySchemes` **and** a `security` requirement; raise loud with a pointer to the fix. **Better:** hoist posture's `_inject_security` into a shared, opt-out spec transform so any authed product gets a default bearer requirement centrally (kills the bug class instead of detecting it). **Effort:** small-medium (spec already loaded; check two keys, or relocate ~12 lines).

---

## Pitfall 4 — Adding one generated-CLI option = lock-step edits across 4-6 hand-maintained mirrors, only one test-coupled `SIMPLIFY` + `HARDEN`

**What.** The CLAUDE.md "6-step recipe" for adding a config option *is the smell*: model field → `default_config.yml` body → its env-var doc header → `_ENV_MAP` → `_BOOL_PATHS`/`_INT_PATHS` → `effective_dict()`. Only the **model ↔ default_config body** coupling is test-enforced (`test_config_packaged_defaults_match_models`). The rest are hand-typed copies of data the models already carry, and they fail by **omission** (the hardest miss to notice): forget the `_ENV_MAP` row → the env var is silently ignored; forget `effective_dict` → `config show` silently drops the field.

**Evidence (single source already exists).**
- `config.py.jinja:88-98` `_ENV_MAP` — all 9 entries are exactly `("configuration", <section>, <key>)`, and `config.py.jinja:343-354` `_known_config_paths()` **already derives that exact set** from `CliConfiguration.model_fields`. `_ENV_MAP` is a hand-typed duplicate of computed data.
- `config.py.jinja:261-276` `effective_dict()` — a 4th by-hand mirror of every field.
- Same pattern elsewhere: `_AUTO_EXPOSED` (`productconfig.py:175-195`) hand-lists context keys and **already drifted** — `has_retry` is injected (`:248`) but unlisted, so a `vars: {has_retry: …}` silently shadows it (the deep-dive admits the hole, `product-config.md:46`). And `scaffold_context._auth_env_vars` (`scaffold_context.py:19-31`) hardcodes ScmOAuth attr names instead of using the `AuthComponent.credential_fields()` contract that exists for exactly this.

**Why it's architectural.** Classic shotgun surgery / single-source-of-truth violation, and it doubles as a silent-drift bug factory. It also throttles every future feature (named environments, logging — both in the project backlog) behind the same 6-edit dance.

**Simplify (and thereby harden).** Derive the mirrors from the models that already hold the truth:
- `_ENV_MAP` ← a comprehension over `_known_config_paths()`; `_BOOL_PATHS`/`_INT_PATHS` ← field annotations; `effective_dict()` ← walk `model_fields`; the env-var doc header ← a Jinja loop over the derived map. Collapses the recipe to **2 steps** (add field + add default entry) — the one coupling a test already enforces. Module stays import-light (only `model_fields`), so the early-load constraint holds.
- `_AUTO_EXPOSED`: delete the literal; capture `reserved = set(context)` immediately before `context.update(cfg.vars)`. Self-maintaining; closes `has_retry`.
- `_auth_env_vars`: build from `loaded.auth.credential_fields()` (each `CredentialField` carries its `env_var`).

**Effort:** medium for the `_ENV_MAP`/`effective_dict` derivation; tiny for `_AUTO_EXPOSED` and `_auth_env_vars`. Highest leverage simplification in the repo.

---

## Pitfall 5 — The quality harness overstates its guarantees; the offline gate is blind to Pitfall 1's failure class `HARDEN`

**What.** The harness markets itself as "the enforcement layer that makes the agent's test-quality guarantees real" (`harness-and-testing.md:3`). Three structural gaps mean the guarantee is weaker than the prose:

- **Frozen oracle is local-only.** Both enforcement points live in `.claude/` and the Stop-gate dirty check sees only the working tree — `fast_gate.py:42-44` uses `git diff --name-only HEAD` + `ls-files --others`, so a *committed* edit to a protected path is invisible. The documented non-bypassable net (CODEOWNERS + branch protection) is admitted as not built (`harness-and-testing.md:92-103`) and `.github/CODEOWNERS` does **not** exist. No CI job re-asserts oracle integrity.
- **Live CRUD gate doesn't exist.** Failure-mode #2 ("unvalidated assumptions about the real API") is defended only by `nox -s live`, which runs on agent discipline + local creds and *skips* (not fails) without them (`noxfile.py:241-247`). `live.yml` is listed as planned and is absent.
- **The gate can't see codegen drift.** As in Pitfall 1, the patch tests re-encode the assumed OAG shape in fixtures, so they drift with the code; the gate stays green through the exact regression class the patches exist to prevent.

**Why it's architectural.** Everything above (Pitfalls 1-4) leans on "the gate / smoke / tests will catch it." This pitfall says: for the highest-severity class, they structurally can't, and the frozen-oracle guarantee has no server-side teeth — a gap the harness doc itself flags as worsening "as model capability rises."

**Harden.**
- Add `.github/CODEOWNERS` over `protected_globs` + a required-review branch-protection rule (the documented design — mostly config). Optionally a CI check: `git diff origin/main -- <globs>` flags any change to a frozen path for human sign-off.
- Add a **behavioral** real-build assertion (oneOf round-trips unwrapped; a lenient enum accepts an unknown value) against actual OAG output — not hand-written fixtures — so an OAG bump turns red. This is the linchpin that makes Pitfall 1's fix observable.
- Either wire `live.yml`, or downgrade CLAUDE.md's "hard phase boundary" language for `live` to "advisory" so the guarantee isn't overstated.

**Effort:** CODEOWNERS/branch-protection low; behavioral real-build test ~½ day; `live.yml` low.

---

# Part II — Validation against incoming specs (adem / ngts / incidents)

**Question posed:** the SDK/CLI generator must flex to varied spec structures. Do the five pitfalls still apply to the not-yet-enrolled specs, or does the variety widen scope — and will the proposed fixes tie into these specs?

**Method:** three parallel spec-fingerprint reviewers parsed each spec and probed it against every hardcoded generator assumption (auth↔spec, codegen patches, classification, envelope, param/body shape). adem is SDK-enrolled (`sdk.yml`+`hooks.py`, no `cli.yml`); ngts and incidents are spec-only stubs.

**Answer: scope increases — decisively, and in a specific place.** The original five were derived from two *CRUD-shaped, enrolled* products. The incoming specs are not CRUD-shaped, and they break the generator's **mapping model**, not just its drift-handling. For one of three this is a *hard build failure*; for the others, *silently-wrong output*. The proposed hardening (fail-loud) is **necessary but not sufficient** — these specs need new *declarative* flex points or they can't be enrolled without re-specifying the API by hand.

## II.1 — Cross-spec fingerprint

| Probe | adem | incidents | ngts | (prisma-browser, ref) |
|---|---|---|---|---|
| operations | 13 (all GET) | 2 | **150** | 95 |
| classify **correctly** | **0 / 13** | **0–1 / 2** | **0 / 150** (123 unmapped + 27 → junk) | (CRUD; works) |
| operationId convention | controller-prefixed `agent_controller_get_agent_metric` | `searchIncidents` / `getIncidentDetails` | **object-first** `certificates_getAll`, +kebab +`v1`-prefixed | verb-first |
| auth | scm_oauth fits ✓ | **static HTTP-bearer — no built-in** | scm_oauth fits ✓ | scm_oauth |
| securitySchemes present? | yes | yes | yes | yes |
| oneOf (discriminated) | 10 (0) | 0 | **18 (11)** | many |
| list-envelope array field | `collection`/`series` | `data` (matches by luck) | **object-named** (`certificates`,`instances`,…) | `data`+`page_info` |
| pagination style | string cursor | **POST-body** `page_number` | `limit`-only / ad-hoc | offset / page_info |
| request bodies | 0 | 1 (inline obj) | 67 (all `$ref`→obj) | many |
| required **header** params | `Prisma-Tenant` ×13 | `X-PANW-Region` | (present; SCM headers) | — |

## II.2 — Do the five still hold?

| Pitfall | adem | incidents | ngts | Net |
|---|---|---|---|---|
| **1 — silent drift seams** | oneOf patches fire (10); enum patches dormant | all patches inert (0 oneOf) | 147 enums rebased, **11 discriminated oneOf to verify** | Holds. **1d (envelope) escalates** to *100% misdetection* (below). Patches scale. |
| **2 — reflection boundary** | — | — | — | **Reinforced** → directly causes **F2** (lossy param location). Freshness guard still applies. |
| **3 — auth silent-401** | N/A (well-formed) | N/A (well-formed) | N/A (well-formed) | **Reframe:** the missing-scheme 401 is *posture-specific*; all 3 incoming specs declare schemes. The real gap is **F3** (one-strategy registry). |
| **4 — multi-site coupling** | — | — | — | Holds; **F1's dual override surface** (`sdk.yml operations:` vs `cli.yml request:`) is the same shotgun-surgery at O(ops) scale. |
| **5 — harness overstated** | — | — | — | Holds; the proposed behavioral real-build test now has concrete targets (11 discriminated-oneOf unwraps, envelope columns, classify coverage). |
| *(introspect phase-2 TODO: non-BaseModel bodies)* | N/A | N/A | N/A | **Deprioritize** — no incoming spec has array/free-form bodies (all `$ref` objects). |

## II.3 — Five flexibility-model gaps the variety reveals (F1–F5)

These are *new* — not silent-drift, but **whole categories of spec shape the generator has no declarative handle for**. The only current flex point for each is per-operation, per-product manual authoring.

**F1 — Classification assumes verb-first English CRUD; real specs aren't → O(ops) hand-work, and a hard build failure for object-first specs. `HARDEN` — now co-most-pressing.**
`_VERB_PREFIXES` matches `create_/patch_/delete_/get_/list_` prefixes (`opmodel/classify.py:16-22`; CLI adds `update_` at `cli/classify.py:70-77`). Incoming specs don't conform: adem **0/13** (controller-prefixed), ngts **123/150 unmapped + 27 classify-to-junk** (object-first `certificates_getAll`), incidents' primary `search_incidents` unmapped. Two compounding facts: (a) classification runs on the **raw** `op.method`, so the `sdk.yml operations:` rename that fixes the SDK facade **does not reach the CLI** (`cli/classify.py` docstring ~:108) — you maintain the mapping *twice*; (b) with `facade: true`, an anchorless op is a **hard build failure** — `wrapper.py:~228` `raise ValueError("…maps to no CRUD object… add sdk.yml operations…")`. Fixing ngts by hand = ~150 `operations:` entries = re-specifying the API.
→ **Missing primitive:** a declarative, spec-level **operationId transform** (pattern rules like `{obj}_getAll→list_{obj}`, `{obj}_getById→get_{obj}`, `{obj}_create→create_{obj}`) applied in `preprocess`, feeding **both** SDK and CLI classification from one source. One rule maps ~110 ngts ops. Today the practical alternative is a per-product `hooks.py` bulk-rewrite — undeclared, untested, per-product.

**F2 — The reflection boundary discards OpenAPI parameter location (`in:`) → required headers/queries collapse to "path" and can hijack `--id`. `HARDEN` (new, direct child of Pitfall 2).**
`introspect.py:224-248` infers location from the *flattened Python signature*: body if BaseModel, else `required→path`, else `query`. It has **no header concept**. So adem's required `Prisma-Tenant` (all 13 ops) and incidents' required `X-PANW-Region` → `location="path"` → become a CLI flag **and** a `detect_id_param` candidate (`opmodel/classify.py:67-79`), so a **transport header can silently become the resource `--id`**. Required *query* params (adem `endpoint-type`, `filter`) hit the same path-misclassification. No knob re-tags a param's location, excludes it from id-detection, or supplies a config-level default header (tenancy headers want to live in config like creds do). Root cause is Pitfall 2: reflecting the SDK signature *loses* what the spec knew.
→ **Missing primitive:** preserve parameter location across the boundary (read it from the spec, or carry it through OAG), **+** a param-location / `exclude-from-id` override, **+** config-supplied default headers.

**F3 — Auth-strategy registry has exactly one entry. `HARDEN` (reframes Pitfall 3).**
`BUILTIN_AUTH = {"scm_oauth": ScmOAuth}` (`config.py:166`). incidents needs a *static HTTP-bearer JWT* — no built-in fits; you'd write a custom component. The "flexible auth" claim holds only for the SCM OAuth family (adem/ngts/prisma/posture). 
→ **Missing primitive:** a pluggable auth-strategy registry with at least `http_bearer` and `api_key` alongside `scm_oauth`.

**F4 — Pagination registry covers only query-offset and `page_info` cursor. `HARDEN`.**
Built-ins: `offset` (query `limit`/`offset`) and `cursor` (`page_info`) (`config.py:69-92`). Incoming styles: incidents paginates via **POST body** (`page_number`/`page_size`), adem via a **string cursor** field, ngts is `limit`-only/ad-hoc. A list op renamed to `list_*` flips on paging (`cli/classify.py:469`) and emits query params the API ignores → **silently no pagination**.
→ **Missing primitive:** pagination strategies for body-driven and string-cursor styles, plus an explicit "unpaginated" declaration so a `list_` op can opt out loudly.

**F5 — Envelope detection (`data` + `page_info`) misdetects ~100% of incoming list responses. `HARDEN` — this is Pitfall 1d, promoted from edge case to dominant.**
`introspect.py:180` treats a list field as an envelope only if named `data` or accompanied by `page_info`. ngts: **no** wrapper uses either — arrays sit under object-named fields (`certificates`, `instances`, `integrationsServices`, …) with `count`/`totalCount` siblings; the field name *varies per endpoint*, so no single literal fixes it. adem: arrays in `collection`/`series`. Result: every `list` command renders **one row with a giant JSON cell** instead of per-item columns, with no override.
→ **Missing primitive:** a "**sole array-typed field ⇒ envelope**" default heuristic in `_response_info`, **+** a per-op `cli.yml items_field:`/cursor override (neither exists today).

*Minor (ngts):* the 4-rule `_singularize` mis-stems real nouns (`status→statu`, `series→sery`, `indices→indice`, `analysis→analysi`), and `_strip_id_suffix` only knows `_by_id/_by_type` (not `_id`, `_by_expression`, or `v1` version tokens) → junk/duplicated objects (`v1-statu`, `…-conf` vs `…-conf-id`). Bounded, but real once F1 is fixed and these nouns surface.

## II.4 — Revised priority given the variety

The five stand, but enrolling the incoming specs reorders what to do first:

1. **F1 (classification) is now co-#1 with Pitfall 1.** It's a *hard build failure* (ngts) / *empty CLI* (adem), not silent — the single biggest blocker to onboarding the new products. The declarative operationId-transform primitive is the highest-leverage single change in this review, and it also collapses F1's dual-override-surface (Pitfall 4).
2. **F5 / Pitfall 1d (envelope):** silently wrong on *every* list command for adem+ngts. The "sole-array-field" heuristic is cheap and fixes most cases without per-op authoring.
3. **F2 (param location):** silent `--id` hijack on every adem op and incidents. Pairs with the Pitfall 2 boundary work.
4. **Pitfall 1 fail-loud + Pitfall 2 freshness:** foundational; the behavioral real-build test (Pitfall 5) gets concrete targets from these specs (the 11 discriminated oneOf wrappers in ngts).
5. **F3 (auth) + F4 (pagination):** needed specifically to enroll **incidents** correctly; lower urgency only because incidents is 2 ops.

**Direct answer to "will the changes tie into these specs?"** The hardening changes alone would make adem/ngts *fail loudly* instead of mis-generating — an improvement, but they still couldn't be enrolled. To actually generate correct SDKs/CLIs for the variety, the **declarative flex points (F1, F2, F5 especially)** must land alongside the hardening. Build them as *spec-level, pattern-based* primitives (one rule for many ops), not as more per-op knobs — otherwise onboarding ngts is ~150 hand-authored entries duplicated across `sdk.yml` and `cli.yml`.

---

## Appendix A — Quick deletions / one-liners (pure wins, do alongside the above)

Surfaced by multiple reviewers; pure subtraction or trivial fixes, no design debate:

- **Provenance lies.** `build.py:109` hardcodes `phantasos_version="0.1.0"`; `pyproject.toml` is `0.1.0a1`. Replace with `importlib.metadata.version("phantasos")` (stdlib). The only `_about.py` test (`test_cli.py:53`) checks the *spec* version, never `PHANTASOS_VERSION` — add that assert. One line + one assert. Defeats the feature's only purpose today.
- **Dead generator knobs.** No product sets a `generator:` block (verified). `library` + `oneof_discriminator_lookup` are dead flexibility threaded through `build → generate → _oag_cmd`. Inline as constants in `generate.py`; keep `apply_generic_patches` (defensible debug toggle).
- **Dead CLI surface.** `Override.variant` (defined, never read — `cliconfig.py:30`), `ParamInfo.union_members` (set, never read — `inventory.py:25`/`introspect.py:252`), `select_method_for_verb` (`# TODO(phase2)`, zero callers — `classify.py:164`), `cli_operations(registry_attr=…)` half-applied knob. Delete.
- **Dead config branch.** `CustomComponent` + the `./`/`.jinja` custom-template path (`productconfig.py:129-152`) has no users **and** is the one component path with `extra="allow"` (a typo'd key isn't rejected, unlike every `extra="forbid"` built-in). Delete until a product needs it.
- **Reinvented stdlib in nox.** `noxfile.py:257-263` hand-rolls `.env` parsing while `python-dotenv` is already installed in that session — `dotenv.dotenv_values(".env")`.
- **No download timeout.** `provision._download_verified` (`provision.py:40`) `urlopen` with no `timeout=` — a stalled mirror hangs the build.

## Appendix B — Layering inversion (already on the cleanup backlog as #11)

`opmodel/` is the documented stage-agnostic base, yet it imports *up* into the CLI leaf: `opmodel/introspect.py:17` (`from ..cli.ir import FlagKind`), `opmodel/inventory.py:9`, `opmodel/classify.py:12`. Move the pure `Literal` vocab (`Verb`/`SubVerb`/`FlagKind`) down into `opmodel`, re-export from `cli.ir`. Restores an acyclic `opmodel → {sdk, cli}` arrow and lets the SDK path use `opmodel` without dragging in `cli.ir`. Tracked in the cleanup report — folding it into a hardening pass here for visibility.

## Appendix C — Anti-scope (do NOT "fix" these)

Carried from the cleanup report's §6 + reviewer confirmation:

- **Do not DRY across `sdk` ↔ `cli`** (`examples.py`, the two `_command_view`s, the `_VERB_PREFIXES` `update_` divergence) — deliberate separation-of-duty. All recommendations above stay within one path or in the shared `opmodel` base.
- **Do not `StrEnum`-ify `Verb`/`SubVerb`/`FlagKind`** as a drive-by — they serialize verbatim into the emitted `ir.json`/`spec.py` (frozen contract). If wanted, do it inside the in-flight CLI IR-deepening work.
- **Do not convert the prefix-loop classifiers to `match`** — already data-driven; `str.startswith` has no clean `match` form.
- **Do not touch frozen oracles** (`.claude/harness.toml` `protected_globs`, including `harness.toml` itself) — surface for human decision.
- **Leave the solid parts alone:** provisioning, smoke isolation, preprocess transforms, `release.yml`, `load_product`, `main()`'s exit-code wrapper, the post-loop IR-resolution passes.

---

## Suggested sequencing (if/when we act)

1. **One-liners (Appendix A) + the freshness guard (Pitfall 2 cheap half) + auth-vs-spec assert (Pitfall 3) + `_AUTO_EXPOSED`/`_auth_env_vars` (Pitfall 4 tiny half).** Small, independently reversible, each removes a live silent-failure path. One PR.
2. **The silent-skip → fail-loud conversions (Pitfall 1 a/b/c) + the behavioral real-build test (Pitfall 5).** They belong together: the test is what makes the fail-loud observable. One PR.
3. **Derive the config mirrors (Pitfall 4 main).** Self-contained template change guarded by the existing defaults-sync test. One PR.
4. **CODEOWNERS + branch protection + `live.yml`/doc downgrade (Pitfall 5).** Mostly config. One PR.
5. **Defer:** subprocess introspection migration (Pitfall 2 longer-term) and the envelope escape hatch (Pitfall 1d) until a concrete need lands.

Every batch respects the branch/release workflow (feature → `develop`, squash, `## [Unreleased]`).
