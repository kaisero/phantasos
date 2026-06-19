# sdk-generator

Validated against 23ec64a on 2026-06-14 · Purpose: how `phantasos sdk build` turns a product's spec into a vendored, scaffolded Python SDK.

## Purpose & responsibilities

`generator/sdk/` owns the end-to-end build that turns one product's OpenAPI spec
into a complete, installable Python SDK project. It preprocesses the spec, runs
OpenAPI Generator (OAG) under a self-provisioned Java toolchain, patches known
codegen bugs, vendors phantasos's component templates (auth, pagination, errors,
facade, retry) into the package, renders the full project scaffold around it, and
smoke-checks the result. The output is a pure build artifact — never hand-edited.

## How it works

`build.build()` in `build.py` is the orchestrator; it runs the stages in order
and returns a stats dict. To trace the pipeline, open these files in sequence:

1. **Preprocess** — `preprocess.load()` then `preprocess.clean()` in
   `preprocess.py` apply the generic, spec-agnostic transforms; the product's
   `transforms:` block drives `preprocess.hoist_items()` / `tag_operations()`,
   and a product `hooks.py::preprocess(spec)` runs last. The result is dumped via
   `preprocess.dump()` to `<out>/.phantasos/preprocessed.yaml`.
2. **Generate** — `generate.write_openapi_generator_ignore()` then
   `generate.generate()` in `generate.py` invoke OAG (python generator).
   Provisioning is lazy and lives in this stage: `generate.generate()` calls
   `provision.resolve_java()` and `generate.ensure_jar()` (see `provision.py`)
   to fetch/verify the pinned JRE and OAG jar on demand.
   `generate.prune_suppressed_files()` then removes any suppressed OAG files left
   by earlier builds.
3. **Patches** — when enabled, `patches.apply_generic_patches()` in `patches.py`
   fixes apostrophe enums, rebases enums onto lenient bases, and rewrites oneOf
   to first-match. It also attaches pydantic `model_serializer`s so `model_dump()`
   unwraps each oneOf wrapper to its `actual_instance` (no scaffolding leak) and
   omits empty `additional_properties` bags (non-empty bags preserved); the wrap
   handler respects `exclude=`, so the `to_dict()` request path is byte-unchanged.
   A product `hooks.py::patch(pkg_dir)` runs after.
4. **Render** — `render.vendor()` in `render.py` writes the selected component
   templates (auth/pagination/errors/facade/retry plus any `include:` files) into
   `<package>/extras/`. At this point `facade._RESOURCES` exists in-process, so
   the docs stage (4a) can run before the scaffold is written.
   4a. **Docs** (config-gated) — when the product's `sdk.yml` has a `docs:` block,
   `docs.build_docs_context()` in `generator/sdk/docs.py` runs a scoped,
   in-process `introspect()` of the configured `showcase_resource`, classifies the
   resource's operations into CRUD slots via `classify_operations()`, and shapes
   a `docs_context` dict (via `shape_context()`) containing `has_docs`,
   `site_name`, `showcase` (per-verb method names, required args, return models,
   `body_code`, and `example_override`), `credentials` (from
   `loaded.auth.credential_fields()`), and `show_pagination_guide`. Products
   without a `docs:` block skip this step entirely — `has_docs` is `False` in the
   scaffold context and all doc templates gate out.

   The `docs:` block in `sdk.yml` accepts two optional keys that sharpen the
   generated docs:

   - **`showcase_variant`** — for oneOf body params, names the concrete variant
     model to use in the synthesized example (e.g. `CustomApplicationInput`
     instead of the opaque wrapper).  Consumed by `build_docs_context()` →
     `shape_context()` → passed as `variant` to `synthesize_body()`.
   - **`examples.<slot>`** — a verbatim, per-operation example string (YAML block
     scalar) that completely replaces the synthesized code block for that CRUD slot
     (`create`, `read`, `update`, `delete`).  Set in `sdk.yml` as
     `docs.examples.create: |  …`; consumed via the `DocsExamples` pydantic model
     in `productconfig.py`.  If set, `example_override` in the context is truthy
     and the CRUD template emits it literally instead of the synthesized call.

   **`examples.py` synthesizer** — `synthesize_body(model, *, variant=None) -> str`
   imports the live pydantic model class from the built SDK, reflects on its
   required fields, and returns a real-shaped constructor expression (e.g.
   `CustomApplicationInput(\n    name="<name>",\n    type="custom",\n    urls=[…],\n)`).
   The `variant` parameter resolves through the oneOf `actual_instance` annotation
   to pick the right concrete class when the body param is a wrapper.

   **Reference generator** — `scripts/gen_ref_pages.py.jinja` (rendered into the
   SDK as `docs/scripts/gen_ref_pages.py`) does two things beyond emitting one
   mkdocstrings page per module:

   1. **griffe-pydantic** — the generated `mkdocs.yml` includes `griffe_pydantic`
      in the mkdocstrings `extensions:` list plus `show_if_no_docstring: true` and
      an aggressive `filters:` blocklist that hides OAG scaffolding fields
      (`actual_instance`, `one_of_schemas`, `oneof_schema_*`, etc.) while keeping
      the user-facing pydantic fields.  griffe-pydantic renders each field's
      `description=` (from the OAS spec) as a proper docstring entry, so the
      reference page for a model like `CustomApplicationInput` shows
      "Name of the application" under the `name` field.
   2. **oneOf wrapper variant-link pages** — when a models/ module defines a
      pydantic model with an `actual_instance: Union[A, B, …]` field (the OAG
      oneOf wrapper pattern), `_oneof_variants()` extracts the union members and
      the page for that module gets an appended "One of the following variants:"
      list with relative links to each variant's own reference page.  This makes
      `CreateOrReplaceAppInput` link directly to `CustomApplicationInput` (and any
      other variants) rather than documenting the opaque wrapper internals.

   Then `scaffold.render_scaffold()` (in the sibling `scaffold` module,
   `phantasos/scaffold.py` — not this package) lays down the project scaffold with
   `{**loaded.context, **docs_context}` as the context (just `loaded.context` for
   non-docs products), and `products/<name>/overrides/` winning over the built-in
   templates.
   The documentation templates live under `src/phantasos/scaffold/docs/` — Home,
   Getting Started, Architecture, authentication/pagination/CRUD guides, a
   `scripts/gen_ref_pages.py` (mkdocs-gen-files + literate-nav reference
   generator), and a `_hooks.py` MkDocs logging filter that silences griffe's
   benign `Duplicate parameter information` warnings so `mkdocs build --strict`
   passes against OAG's sphinx docstrings. All templates are gated on
   `{% if has_docs | default(false) %}` (mandatory `| default(false)` because the
   scaffold engine uses `StrictUndefined`); when `has_docs` is false they render
   to whitespace and `render_scaffold` skips the file. The `nox -s sdk-docs`
   session is the integration gate: it performs a real SDK build, then runs
   `mkdocs build --strict` in the output directory and asserts: (A) a leaf model
   page (`custom_application_input`) contains a real field description
   (griffe-pydantic working); (B) the `create_or_replace_app_input` wrapper page
   links `CustomApplicationInput` (oneOf variant pages working); (C) the CRUD
   guide's create block contains the curated value "Acme Wiki" and does not contain
   the opaque `CreateOrReplaceAppInput(...)` placeholder.
5. **Provenance** — `build.build()` writes `<package>/_about.py` with the spec,
   phantasos, and OAG versions.
6. **Smoke** — `smoke.smoke()` in `smoke.py` counts operations and (unless
   `run=False`) import-walks every module in an isolated `pip install`ed venv.

## Build / run pointers

- Build the example SDKs: `uv run nox -s smoke` (auto-provisions JRE; needs network).
- One product: `phantasos sdk build <name>` (`--no-smoke` to skip the import-check).
- Unit tests: `uv run nox -s gate` (offline) or `pytest tests/test_generate.py …`.

## Module map

<!-- GENERATED:module-map -->
- `build.py` — SDK build orchestrator: preprocess -> generate -> patch -> vendor -> scaffold.
- `docs.py` — Scoped introspect + verb classification + docs context for generated SDKs.
- `examples.py` — Synthesize illustrative constructor examples from live pydantic models.
- `generate.py` — Run OpenAPI Generator (python) — jar fetch/verify + invocation.
- `patches.py` — Generic codegen-bug patches for OpenAPI Generator (python) output.
- `preprocess.py` — Spec preprocessing — generic transforms + parameterized spec-specific helpers.
- `provision.py` — Provision the Java toolchain for OpenAPI Generator.
- `render.py` — Vendor step: render selected component templates into the SDK's extras/.
- `smoke.py` — Smoke check: import every generated module (in isolation) and count operations.
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
- `build.py`
  - `build(loaded, run_smoke)`
- `docs.py`
  - `classify_operations(operations, resource, overrides)` — Map each CRUD slot to its canonical OperationInfo (present slots only).
  - `shape_context(inventory, resource, site_name, auth, overrides, has_pagination, resolve, variant, examples)`
  - `build_docs_context(loaded, project_dir)` — Scoped introspect of the showcase resource -> docs context dict.
- `examples.py`
  - `synthesize_body(model, variant)` — Real-shaped constructor expression for ``model`` (required fields only).
- `generate.py`
  - `write_openapi_generator_ignore(out_dir)` — Suppress OAG's supporting files so phantasos's scaffold owns them.
  - `prune_suppressed_files(out_dir)` — Delete any pre-existing copies of the suppressed OAG files.
  - `ensure_jar()`
  - `generate(spec_path, out_dir, package, library, oneof_discriminator_lookup)`
- `patches.py`
  - `patch_apostrophe_enums(models_dir)`
  - `rebase_lenient_enums(pkg_dir)`
  - `patch_oneof_first_match(models_dir)`
  - `patch_oneof_unwrap_serializer(models_dir)` — Attach a plain model_serializer to each oneOf wrapper so model_dump unwraps.
  - `patch_drop_empty_additional_properties(models_dir)` — Attach a wrap model_serializer dropping empty additional_properties bags.
  - `apply_generic_patches(pkg_dir)`
- `preprocess.py`
  - `load(path)`
  - `dump(spec, yaml, path)`
  - `collapse_allof(schemas, node, stats)` — Collapse `allOf` whose single structural branch resolves to a non-object.
  - `fix_strings_and_enums(node, stats)` — Repair mojibake strings and dedupe enum members (after repair).
  - `clean(spec, stats)` — Run all generic, spec-agnostic transforms.
  - `hoist_items(spec, hoists, stats)` — Hoist nested inline array-item objects into named components.
  - `tag_operations(spec, ops, stats)` — Add tags + operationId to operations that lack them.
- `provision.py`
  - class `ProvisionError` — Raised when the Java toolchain cannot be provisioned.
  - `cache_dir()` — Shared on-disk cache for the OAG jar and the managed JRE.
  - `resolve_java()` — Return a path to a usable `java`, provisioning a pinned Temurin JRE if needed.
- `render.py`
  - `vendor(pkg_dir, loaded)`
- `smoke.py`
  - class `SmokeError` — Raised when the isolated smoke environment cannot be provisioned.
  - `smoke(project_dir, package, run)` — Verify a built SDK: count operations and (unless skipped) import-walk it.
<!-- /GENERATED:api -->

## Gotchas / invariants

- **The generated SDK is never hand-edited.** It is a pure build artifact —
  everything (tests, `pyproject.toml`, workflows, `README.md`) is regenerated on
  every `phantasos sdk build`. All customisation lives in `products/<name>/` or
  `src/phantasos/scaffold/` (see `docs/authoring.md`).
- **OAG's own supporting files are suppressed**, not used: `setup.py`,
  `setup.cfg`, `requirements.txt`, `test-requirements.txt`, `tox.ini`,
  `git_push.sh`, the CI workflows, and `README.md` (the full `_OAG_IGNORE` list
  in `generate.py`) are listed in `.openapi-generator-ignore` so the phantasos
  scaffold owns them; `prune_suppressed_files()` also deletes stale copies left
  by earlier builds.
- **JRE and OAG jar are pinned and cached** under `~/.cache/phantasos`
  (override the dir with `PHANTASOS_CACHE`). The Temurin JRE 17 and the OAG jar
  are checksum-verified on download; set `PHANTASOS_JAVA` to use your own JVM.
- **Smoke runs in an isolated venv** built from the SDK's own `pyproject.toml`
  (`pip install <project_dir>`), so phantasos needs none of the SDK's runtime
  deps; skip it with `--no-smoke` / `run_smoke=False` / `PHANTASOS_SKIP_SMOKE`.
- **Generic patches are idempotent** and spec-agnostic, so re-running a build is
  safe.

## See also

- Specs: `docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md`
- Decisions: (added in the scale increment) `decisions.md`
- Rules: `CLAUDE.md`
