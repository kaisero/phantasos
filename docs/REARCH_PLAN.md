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

## Phase F — Split prisma-browser into its own repo
- Move prisma-browser's `sdk.py` + spec + generated SDK + `.env.example` to a separate repo
  (or a clearly separate top-level dir for now); framework repo retains only `sdkgen/` +
  templates + tests + docs.
- **Acceptance:** from a clean checkout of the framework, `sdkgen build <external sdk.py>`
  produces the prisma-browser SDK; framework repo has zero prisma-/SASE-specific code.

## Phase G — Second-spec validation (deferred until a 2nd spec exists)
- Onboard a genuinely different OpenAPI spec; add component types as its auth/pagination/error
  shapes demand. This is the real test of the pluggable contracts; expect interface revisions.
- **Acceptance:** a non-SASE SDK builds + smokes without modifying spec #1.

## Parity & rollback
- The committed prisma-browser SDK on `migrate/openapi-generator-python` is the **oracle** and
  stays untouched until Phase D passes. Abort = keep the current working SDK.

## Out of scope
- Non-`build` CLI verbs (`new`/`validate`), publishing to PyPI, async client variant,
  discriminator-based oneOf — all deferred (see ARCHITECTURE §8 and prior phase docs).
