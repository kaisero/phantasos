# Re-architecture plan — single-spec generator → `sdkgen` framework

Companion to [`ARCHITECTURE.md`](ARCHITECTURE.md). Phased, end-to-end executable, with a
**parity gate**: the framework must reproduce today's prisma-browser SDK before anything is
removed. Work would happen on a new branch off `migrate/openapi-generator-python`.

Guiding principle: **prove the abstraction reproduces the known-good SDK byte-for-byte
before extracting prisma-browser out.** Keep the current working SDK as the oracle.

## Phase A — Framework package skeleton (`sdkgen/`)
- Create `sdkgen/` with `SdkConfig` + component param dataclasses (`config.py`), component
  interfaces (`components/_interfaces.py`), and module stubs (`generate.py`, `preprocess.py`,
  `patches.py`, `smoke.py`, `cli.py`).
- Move the **generic** logic in unchanged: spec transforms (collapse/mojibake/dedupe) from
  `preprocess_spec.py`; codegen patches (apostrophe/lenient/oneOf) from `apply_patches.py`;
  smoke from `tools_smoke.py`; jar fetch/pin + OAG call from the `Makefile`.
- **Acceptance:** `import sdkgen` works; `sdkgen.patches`/`sdkgen.preprocess` helpers unit-test
  against fixtures identically to today.

## Phase B — Componentize the overlay (templates)
- Convert `overlay/{auth,pagination,errors,facade}.py` into Jinja templates under
  `sdkgen/components/`, lifting the hard-coded SASE constants to template params
  (token_url, scope_env, base_url, data_field, cursor_path, message_path, …).
- Add template-render tests: rendering with the SASE params yields code equal to today's overlay.
- **Acceptance:** rendered components are byte-identical to the current `overlay/` files.

## Phase C — Express prisma-browser as a spec config
- Author `specs/prisma-browser/sdk.py`: `CONFIG = SdkConfig(...)` (SASE auth/pagination/errors
  params, package `prisma_browser`, base URL) + `preprocess()` holding the `HOISTS` and
  `tag_operations` data (calling `sdkgen.preprocess` helpers).
- **Acceptance:** `sdk.py` imports; CONFIG validates.

## Phase D — `sdkgen build` + PARITY GATE
- Implement `sdkgen build ./sdk.py`: preprocess → generate → patch → vendor → smoke.
- Run it for prisma-browser. **Compare the output tree hash to the current committed
  `prisma-browser-sdk/`** (the oracle).
- **Acceptance (the gate):** generated package is **byte-for-byte identical** (or a reviewed,
  explained diff); `make test`-equivalent passes; live read-smoke passes. No prototype code
  removed until this is green.

## Phase E — Package the framework as a CLI
- `pyproject.toml` with `console_scripts: sdkgen = sdkgen.cli:main`; jar cache in
  `~/.cache/sdkgen`; Java preflight with a clear error; `pip install -e .` usable.
- Docs: "authoring a `sdk.py`" + component param reference.
- **Acceptance:** `pip install -e . && sdkgen build specs/prisma-browser/sdk.py` reproduces Phase D.

### Phase E sign-off (PASSED)
- `pyproject.toml` added (hatchling): `console_scripts sdkgen = sdkgen.cli:main`; runtime deps
  `ruamel.yaml`, `jinja2`; the 5 `.jinja` component templates ship as package data (verified in
  the built wheel). Jar cache (`~/.cache/sdkgen`, overridable via `SDKGEN_CACHE`) and Java
  preflight (`check_java`) already live in `generate.py`.
- `pip install -e ".[generated]"` then the installed `sdkgen build` reproduced Phase D exactly:
  427 modules imported, 0 failures, 95 operations; the same 6 behavior-neutral `extras/`+`_lenient`
  files differ from the oracle, all other files byte-identical.
- Authoring guide: [`AUTHORING_A_SPEC.md`](AUTHORING_A_SPEC.md).

## Phase F — Split prisma-browser into its own repo
- Move prisma-browser's `sdk.py` + spec + generated SDK + `.env.example` to a separate repo
  (or a clearly separate top-level dir for now); framework repo retains only `sdkgen/` +
  templates + tests + docs.
- **Acceptance:** from a clean checkout of the framework, `sdkgen build <external sdk.py>`
  produces the prisma-browser SDK; framework repo has zero prisma-/SASE-specific code.

### Phase F sign-off (PASSED — adapted)
Chosen variant (per maintainer): **sibling directory now**, not a separate repo, and the
**spec config stays in the framework repo as the example spec** (rather than being moved out
entirely). This keeps a runnable end-to-end example in-repo while still removing all generated
output and the legacy pipeline.

- The repo was renamed `pan-pab-sdk` → `sdk-gen`. The generated SDK is **never** kept in it.
- Extracted to the sibling `../prisma-browser-sdk/` (its own self-contained project): the
  generated `prisma_browser/` + scaffolding, the 6 SDK-specific tests + an SDK-pointing
  `conftest`, `examples/` (with `_common.py` repointed at the local package), and `.env.example`.
- Removed the 1st-prototype single-spec pipeline (superseded by `sdkgen/`): `Makefile`,
  `preprocess_spec.py`, `apply_patches.py`, `tools_smoke.py`, `overlay/`, `findings/`, and the
  committed `*.preprocessed.yaml`. Rewrote `README.md` (framework) and CI (`pytest tests/` +
  `sdkgen build` smoke). Kept all of `docs/` (incl. the prototype phase history).
- The example spec lives at `specs/prisma-browser/{sdk.py,prisma-browser.yaml}`; `sdk.py`
  resolves the spec relative to its own dir and sets `project_dir` to the sibling.
- **Genericity check:** `grep -riE 'prisma|sase|tsg|paloalto' sdkgen/ tests/` returns nothing —
  the framework package and its tests carry **zero** spec-specific code. (Spec-specific content
  lives only under `specs/`, by design.)
- **Acceptance:** `sdkgen build specs/prisma-browser/sdk.py` builds into the sibling (427
  modules, 0 failures, 95 ops), nothing leaks into the framework repo; framework tests 7 passed;
  sibling SDK tests 16 passed.

## Phase G — Second-spec validation (deferred until a 2nd spec exists)
- Onboard a genuinely different OpenAPI spec; add component types as its auth/pagination/error
  shapes demand. This is the real test of the pluggable contracts; expect interface revisions.
- **Acceptance:** a non-SASE SDK builds + smokes without modifying spec #1.

## Parity & rollback
- The committed prisma-browser SDK on `migrate/openapi-generator-python` is the **oracle** and
  stays untouched until Phase D passes. Abort = keep the current working SDK.

### Phase D parity sign-off (PASSED)
`sdkgen build specs/prisma-browser/sdk.py` was run against the oracle (`prisma-browser-sdk/`):

- **Generated code: byte-for-byte identical.** Every OpenAPI-Generator output file (`api/`,
  `models/`, `api_client.py`, `configuration.py`, `rest.py`, `exceptions.py`, …) matches the
  oracle exactly. File sets are identical (no missing/extra files). Preprocess stats:
  24 allOf collapsed, 2 mojibake fixed; patches: 1 apostrophe, 124 lenient enums, 9 oneOf.
- **Behavioral parity.** The full offline suite (`tests/`, 16 SDK + 7 framework = 23 tests)
  passes with `SDK_UNDER_TEST` pointed at the freshly built SDK. Smoke: 427 modules imported,
  0 failures, 95 operations.
- **Reviewed, explained diff (accepted).** Only 6 hand-written files differ, all behavior-neutral:
  - `extras/{auth,errors,pagination,facade}.py`, `extras/__init__.py`, `_lenient.py` —
    docstrings/comments were genericized in the framework templates (terser, not prisma-specific).
  - `extras/auth.py` — `ValueError("scope is required")` drops the prisma-specific
    `e.g. 'tsg_id:1234567890'` example (now generic).
  - `extras/facade.py` — `_RESOURCES` is **alphabetical** (auto-discovered from the generated
    `api/` package) vs. the oracle's hand-curated order. Behavior-neutral: the dict is iterated
    only to `setattr` attributes; `client.<resource>` access is unaffected.
  - Type annotations and all executable code are otherwise identical (verified by AST-normalized
    comparison that strips docstrings/comments). The provenance file `_about.py` is new (expected).

  Decision: keep the templates generic and accept this diff rather than baking prisma-specific
  prose / a curated resource order into the framework. Revisit prose genericity at spec #2 (Phase G).

## Out of scope
- Non-`build` CLI verbs (`new`/`validate`), publishing to PyPI, async client variant,
  discriminator-based oneOf — all deferred (see ARCHITECTURE §8 and prior phase docs).
