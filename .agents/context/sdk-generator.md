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
   `<package>/extras/`. Then `scaffold.render_scaffold()` (in the sibling
   `scaffold` module, `phantasos/scaffold.py` — not this package) lays down the
   project scaffold, with
   `products/<name>/overrides/` winning over the built-in templates.
5. **Provenance** — `build.build()` writes `<package>/_about.py` with the spec,
   phantasos, and OAG versions.
6. **Smoke** — `smoke.smoke()` in `smoke.py` counts operations and (unless
   `run=False`) import-walks every module in an isolated `pip install`ed venv.

**Typed wrapper context (`wrapper.py`).** Building on the `operations:` override
validator, `wrapper.build_wrapper_context(inv, overrides, discovered)` produces the
in-memory render context for the typed `client.<object>.<verb>(...)` wrappers
(template rendering lands later). It groups ops by their **classified object**
(`classify_name(...).object`), not by the raw `op.resource` api-class attr — one
`*Api` class backs several objects — and resolves each object's backing api class by
joining `op.resource` against `render._discover_resources()`. Each `(object, method)`
unions the params of every backing raw op into one `MethodView` with a list of
`Binding`s (multi-binding: e.g. `application.get` collapses `get_application_by_id` +
`get_application_by_type_and_id`); every unioned non-body param is forced optional and
the body param is renamed to `body`. `ParamView` annotations come from the **live
introspected types** (`typing.get_type_hints(method, include_extras=False)`), never
from the unparseable `ParamInfo.annotation` repr. None-classified ops (PUT `update_*`
-> `replace`; verb-phrase actions like `suspend_devices` -> `device.suspend`) attach to
an EXISTING CRUD object via verb-token stripping — or, when anchorless (`*_positions`,
`publish_draft_configuration`), require an explicit `sdk.yml operations:` override or the
build fails. `_gate_collisions` rejects a duplicate method name within one object.

## Build / run pointers

- Build the example SDKs: `uv run nox -s smoke` (auto-provisions JRE; needs network).
- One product: `phantasos sdk build <name>` (`--no-smoke` to skip the import-check).
- Unit tests: `uv run nox -s gate` (offline) or `pytest tests/test_generate.py …`.

## Module map

<!-- GENERATED:module-map -->
- `build.py` — SDK build orchestrator: preprocess -> generate -> patch -> vendor -> scaffold.
- `generate.py` — Run OpenAPI Generator (python) — jar fetch/verify + invocation.
- `patches.py` — Generic codegen-bug patches for OpenAPI Generator (python) output.
- `preprocess.py` — Spec preprocessing — generic transforms + parameterized spec-specific helpers.
- `provision.py` — Provision the Java toolchain for OpenAPI Generator.
- `render.py` — Vendor step: render selected component templates into the SDK's extras/.
- `smoke.py` — Smoke check: import every generated module (in isolation) and count operations.
- `wrapper.py` — SDK operation-override helpers + object-granular wrapper render context.
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
- `build.py`
  - `build(loaded, run_smoke)`
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
- `wrapper.py`
  - `validate_override_keys(inv, overrides)` — Raise ``ValueError`` if any override key is not a valid ``resource.method``.
  - class `ParamView` — One render-ready parameter of a wrapper method.
  - class `Binding` — One raw op backing a (possibly multi-binding) wrapper method.
  - class `MethodView` — One typed wrapper method on an object (``client.<object>.<name>(...)``).
  - class `ObjectView` — A typed wrapper class for one classified object.
  - `build_wrapper_context(inv, overrides, discovered)` — Build the object-granular wrapper render context for a built SDK.
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
