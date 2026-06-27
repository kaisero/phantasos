# sdk-generator

Validated against 8ab9ccf on 2026-06-25 · Purpose: how `phantasos sdk build` turns a product's spec into a vendored, scaffolded Python SDK.

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

> **Single-spec vs federated.** A product with a `spec:` runs the single-spec path
> (`_build_single`). A product with `subpackages:` (e.g. `prisma-access`) runs
> `_build_federated`: it loops each sub-package through the shared generate→patch→
> vendor→`_about` core (`_generate_one`), emitting `<package>/<slug>/…` via a dotted
> `--package-name`, then scaffolds the one distribution. Each sub is vendored with
> `suppress_auth=True` (facade `has_auth=False`, no `auth.py`) and its own per-sub
> `operations:` overrides; `vendor`/`patches` take the dotted `package` +
> `distribution_root` so nested-package imports (`_lenient`, resource model imports,
> introspection root) resolve. After the loop, **`runtime.hoist_runtime()`** collapses
> the N near-identical OAG runtime copies (`api_client`, `configuration`, `rest`,
> `exceptions`, `api_response`) into one shared `<package>/_runtime/` and repoints
> every runtime-targeting import (incl. each sub's `__init__.py` re-exports) to
> absolute `<package>._runtime.X` via a libcst transformer (see `runtime.py`). Then
> `_render_shared_auth()` renders the one `<package>/_auth.py` (the bearer/config
> factories — `federated=True`, `has_retry=False`), and `_render_composer()` writes
> the composing `<package>/__init__.py` **last** (overwriting OAG's empty parent
> stub): a `Client` that builds ONE `SdkConfiguration` + ONE `RESTClientObject` pool
> fanned out to N thin `_BearerApiClient` handles (each tagged `.models`), injected
> into each sub's facade `Client`, plus the `_SUBPACKAGES` registry (slug → facade
> `Client`) that docs/CLI enumerate. The first sub-facade wires `default_retry()`
> onto the shared config, since `_auth.py` rendered without it.

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
   `<package>/extras/`. When the facade is enabled, vendoring happens in **two
   passes**: pass 1 emits a raw-only `facade.py` (exposes only `_RESOURCES`, no
   wrapper imports) so the package is importable by `introspect()`; then
   `_vendor_resources()` introspects the pass-1 package via `generator/opmodel/`
   to build the wrapper context (`build_wrapper_context`), renders
   `extras/resources.py` (the object-granular typed resource wrappers); finally
   pass 2 re-renders `facade.py` in full — binding `client.<object>` to the typed
   wrappers via `_WRAPPERS`, while retaining `_RESOURCES` for backward
   compatibility. `_invalidate_pkg_modules` drops stale pass-1 module objects from
   `sys.modules` so the next import re-reads the pass-2 facade from disk. Then
   `scaffold.render_scaffold()` (in the sibling `scaffold` module,
   `phantasos/scaffold.py` — not this package) lays down the project scaffold,
   with `products/<name>/overrides/` winning over the built-in templates.

   > **Docs stage (config-gated; wrapper-driven).** When a product's `sdk.yml`
   > carries a `docs:` block, `build()` runs a docs stage between vendor and
   > scaffold (`build.py:~97`, only if `cfg.docs is not None`): it calls
   > `docs.build_docs_context(loaded, project_dir)` and merges the result into the
   > render context, so the gated `scaffold/docs/*.jinja` templates emit a
   > strictly-building MkDocs-Material site (Home, Getting-Started, Architecture,
   > Guides {auth, pagination, CRUD}, mkdocstrings Reference). The whole site
   > teaches the **wrapper surface** `client.<object>.<clean_verb>(...)`, never the
   > raw `*Api`. `build_docs_context` introspects the SDK's `_WRAPPERS` registry
   > via `cli_operations` (which stamps each op with its
   > `object_attr`/`clean_method`/`has_body` routing); the author-named
   > `docs.showcase_resource` is a **singular wrapper-object key** (e.g.
   > `application`, validated against `_WRAPPERS`, fail-fast). For a **federated**
   > distribution the facade/IR/models live under `<package>.<sub>.*`, so
   > `docs.showcase_subpackage` (e.g. `objects`) retargets the
   > `_wrapper_objects`/`cli_operations`/`models`-import at `<package>.<sub>`; the
   > showcase then carries a clean `attr` (the object id) plus a dotted `call_path`
   > (`<sub>.<object>`) so the guides render `client.objects.address.<verb>(...)`.
   > Single-spec products leave `showcase_subpackage` unset — `call_path == attr`,
   > targeting is byte-identical. `classify_operations`
   > maps each op's CLEAN verb to a CRUD slot directly (create/get→read/list/
   > update/delete) — no raw-prefix verb heuristic — picking the fewest-path-params
   > binding per verb; `_op_dict` emits the wrapper call shape (request body under
   > the `body` kwarg + required path params). The `examples.py` synthesizer
   > (surface-independent) turns each body model into a real-shaped constructor;
   > `docs.examples.<slot>` can override a slot verbatim. The API Reference
   > (`scripts/gen_ref_pages.py.jinja`) autodocs one mkdocstrings page per
   > `<Object>Resource` (keyed off `_WRAPPERS`) + every `models/` module — NOT the
   > raw `api/` classes or the `extras` helpers (those are taught in the guides).
   > It runtime-detects federation via `_SUBPACKAGES` on the imported package: a
   > federated distribution loops the sub-packages and groups every wrapper + model
   > page under `reference/<slug>/…`; a single-spec package renders flat
   > (byte-identical to the pre-federation output).
   > Per-method wrapper docstrings carry, beyond each op `summary`, a synthesized
   > `**Example:**` block (`examples.reference_example`, threaded via `wrapper.py`'s
   > `_reference_example_for`, gated on `docs`): the `client.<object>.<verb>(...)`
   > call with required path args + a `body=` from `synthesize_body`. An empty
   > all-optional body renders `body=Model()  # all fields optional` (not suppressed);
   > the showcase resource honors `docs.showcase_variant` and `docs.examples.<slot>`
   > (shown verbatim, even for `update`). The reference pages also render the typed
   > signature with clickable request-body model cross-refs via three `mkdocs.yml`
   > mkdocstrings keys (`show_signature_annotations`/`separate_signature`/
   > `signature_crossrefs`). The `!^_` filter hides wrapper internals
   > (`_bindings`/`_serialize`/`_select`/…). The `sdk-docs` nox session builds the
   > real prisma-browser SDK (single-spec, flat reference) **and** the federated
   > prisma-access SDK (12 sub-packages → `reference/<slug>/…`) with docs ON and
   > asserts `mkdocs build --strict`; the prisma-access `[[sdk-docs.assert]]` guards
   > check `search/search_index.json` for the per-sub `reference/<slug>/` prefixes,
   > proving each federated sub renders at least one reference page.
5. **Provenance** — `build.build()` writes `<package>/_about.py` with the spec,
   phantasos, and OAG versions.
6. **Smoke** — `smoke.smoke()` in `smoke.py` counts operations and (unless
   `run=False`) import-walks every module in an isolated `pip install`ed venv.

**Shared op-model (`generator/opmodel/`).** The classifier core and introspector
that both SDK-gen and CLI-gen consume live in a stage-agnostic sibling package
(`generator/opmodel/`), NOT inside `generator/cli/`. It provides:
`classify.classify_name` (prefix-heuristic: `create_` / `patch_` / `delete_` /
`get_` / `list_` → verb + sub_verb + singularized object), `classify.OBJECT_OF`
(CRUD object for a raw method, never guesses for non-CRUD ops),
`classify.detect_id_param`, `introspect.introspect` (import-walks an
`*Api`-registry and returns an `OperationInventory`), and the `inventory` types
(`OperationInfo`, `ParamInfo`, `FieldInfo`, `OperationInventory`). It also owns two
base-layer modules: `vocab.py` — the canonical classification-vocabulary `Literal`
aliases `Verb` / `SubVerb` / `FlagKind` (kept BYTE-IDENTICAL in `cli/ir.py` because
that file is copied verbatim into each emitted CLI's `_generated/spec.py`, which
has no `opmodel` to import) — and `_pathutil.py` — the `on_sys_path(path)` context
manager that temporarily front-loads a built SDK onto `sys.path` (the single guard
reused by `introspect`, `cli.classify.cli_operations`, and
`cli.modelschema.build_model_registry`, replacing a 3×-duplicated try/finally).
The `generator/cli/introspect.py` and `generator/cli/inventory.py` modules are now
thin backward-compatibility shims that re-export from `generator/opmodel/`.

The layering is now **acyclic** — `opmodel -> {sdk, cli}` — with `opmodel` no
longer importing up into `cli`. The SDK consumers import opmodel directly:
`sdk/examples.py` and `sdk/wrapper.py` pull their introspect helpers from
`..opmodel.introspect` (not via the `cli` shim). The one remaining `cli`-shim edge
inside `sdk/` is `sdk/docs.py`, which still reaches `cli.classify.cli_operations` /
`cli.inventory` for its wrapper-driven docs context (deliberately left as-is).

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

Beyond the structural `MethodView`/`Binding` fields, `build_wrapper_context`
precomputes the **render-ready strings** the resource template interpolates
verbatim (the template stays a dumb interpolator): per `MethodView` a typed `sig`
(every param optional; `list` adds `*, all_pages: bool = False`), a `return_expr`,
a `present_expr` (the `{...}` set of non-None args, driving binding selection) and
a `call_dict`; per `ObjectView` a `bindings_literal` — the `_bindings` class-var
dict (`verb -> [binding-dict]`) where each binding records its `raw_method`,
`serialize_name`, `requires`, the wrapper→raw `param_map`, the raw `body` param
name, and the `enums` (wrapper-name → enum class) to coerce. `_classname` emits
`<PascalObject>Resource` (e.g. `ApplicationResource`). The emitted
`components/facade/resource.py.jinja` builds one `<Object>Resource` per object
whose clean typed methods delegate to generic `_select`/`_to_raw`/`_call`/`_fetch`/
`_list` helpers: `_select` picks the most-specific binding whose `requires ⊆
present` (so `list`/`get`/`delete` dispatch by which args are present, never
`bindings[0]`), `_to_raw` renames + enum-coerces onto the chosen op's raw params
(routing a discriminator like `type` to path on `*_by_type` vs query on the plain
op, since each binding's `param_map` is its own accepted surface), and
`list(all_pages=True)` paginates via the vendored `paginate(...)` and returns
`page.model_copy(update={"data": items})`. Raw method names appear only inside
`_bindings`. `_serialize(verb, **kwargs)` is the dry-run twin (calls the op's
`*_serialize`).

## Build / run pointers

- Build the example SDKs: `uv run nox -s smoke` (auto-provisions JRE; needs network).
- One product: `phantasos sdk build <name>` (`--no-smoke` to skip the import-check).
- Unit tests: `uv run nox -s gate` (offline) or per-stage suites —
  `tests/test_generate.py`, `tests/test_sdk_preprocess.py` (direct preprocess unit
  tests), `tests/test_sdk_patches.py`, `tests/test_sdk_wrapper.py`,
  `tests/test_sdk_build.py`. The `slow` marker tags the OAG-jar builds
  (deselect with `-m "not slow"`).

## Module map

<!-- GENERATED:module-map -->
- `build.py` — SDK build orchestrator: preprocess -> generate -> patch -> vendor -> scaffold.
- `docs.py` — Wrapper-driven docs context for generated SDKs.
- `examples.py` — Synthesize illustrative constructor examples from live pydantic models.
- `generate.py` — Run OpenAPI Generator (python) — jar fetch/verify + invocation.
- `patches.py` — Generic codegen-bug patches for OpenAPI Generator (python) output.
- `preprocess.py` — Spec preprocessing — generic transforms + parameterized spec-specific helpers.
- `provision.py` — Provision the Java toolchain for OpenAPI Generator.
- `render.py` — Vendor step: render selected component templates into the SDK's extras/.
- `runtime.py` — Federated runtime-hoist pass (libcst).
- `smoke.py` — Smoke check: import every generated module (in isolation) and count operations.
- `wrapper.py` — SDK operation-override helpers + object-granular wrapper render context.
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
- `build.py`
  - `build(loaded, run_smoke)`
- `docs.py`
  - `classify_operations(operations, obj)` — Map each CRUD slot to the wrapper op (clean verb) for `obj` (present only).
  - `shape_context(inventory, obj, site_name, auth, has_pagination, resolve, variant, examples, subpackage)`
  - `build_docs_context(loaded, project_dir)` — Wrapper introspect of the showcase object -> docs context dict.
- `examples.py`
  - `synthesize_body(model, variant)` — Real-shaped constructor expression for ``model`` (required fields only).
  - `reference_example(attr, method, path_args, body_model, variant, override)` — The `**Example:**` block for one wrapper op (always returns a block here).
  - `assemble_reference_docstring(summary, example)` — Combine the one-line summary with an example block into a docstring body.
- `generate.py`
  - `write_openapi_generator_ignore(out_dir)` — Suppress OAG's supporting files so phantasos's scaffold owns them.
  - `prune_suppressed_files(out_dir)` — Delete any pre-existing copies of the suppressed OAG files.
  - `ensure_jar()`
  - `generate(spec_path, out_dir, package, library, oneof_discriminator_lookup, skip_validate_spec)`
- `patches.py`
  - `patch_apostrophe_enums(models_dir)`
  - `rebase_lenient_enums(pkg_dir, package)`
  - `patch_oneof_first_match(models_dir)`
  - `patch_oneof_unwrap_serializer(models_dir)` — Attach a plain model_serializer to each oneOf wrapper so model_dump unwraps.
  - `patch_drop_empty_additional_properties(models_dir)` — Attach a wrap model_serializer dropping empty additional_properties bags.
  - `apply_generic_patches(pkg_dir, package)`
- `preprocess.py`
  - `load(path)`
  - `dump(spec, yaml, path)`
  - `collapse_allof(schemas, node, stats)` — Collapse `allOf` whose single structural branch resolves to a non-object.
  - `fix_strings_and_enums(node, stats)` — Repair mojibake strings and dedupe enum members (after repair).
  - `strip_external_tags(spec, stats)` — Remove the non-standard top-level `ExternalTags` key (trips OAG validation).
  - `clean(spec, stats)` — Run all generic, spec-agnostic transforms.
  - `hoist_items(spec, hoists, stats)` — Hoist nested inline array-item objects into named components.
  - `normalize_operation_ids(spec, strip_suffix, dots_to_underscore, unify_separator, stats)` — Rewrite every operation's ``operationId`` for OAG-friendly method names.
  - `fold_server_prefix(spec, base_url, stats)` — Fold a spec's ``servers[]`` URL path-prefix into every operation path.
  - `resolve_sub_host(spec, base_url)` — The host a federated sub should use.
  - `spec_declares_header(spec, header_name)` — True if the spec declares ``header_name`` as an ``in: header`` parameter.
  - `flatten_scm_bodies(spec, stats)` — Lift oneOf/anyOf leaf properties back onto an SCM "configurable object".
  - `tag_operations(spec, ops, stats)` — Add tags + operationId to operations that lack them.
- `provision.py`
  - class `ProvisionError` — Raised when the Java toolchain cannot be provisioned.
  - `cache_dir()` — Shared on-disk cache for the OAG jar and the managed JRE.
  - `resolve_java()` — Return a path to a usable `java`, provisioning a pinned Temurin JRE if needed.
- `render.py`
  - `vendor(pkg_dir, loaded, package, context, distribution_root, suppress_auth, operations, wrapper_objects)` — Render the selected component templates into ``<pkg>/extras/``.
- `runtime.py`
  - `hoist_runtime(project_dir, root_package, slugs)` — Collapse the per-sub OAG runtime into one shared ``<root>/_runtime/``.
- `smoke.py`
  - class `SmokeError` — Raised when the isolated smoke environment cannot be provisioned.
  - `smoke(project_dir, package, run)` — Verify a built SDK: count operations and (unless skipped) import-walk it.
- `wrapper.py`
  - `validate_override_keys(inv, overrides)` — Raise ``ValueError`` if any override key is not a valid ``resource.method``.
  - class `ParamView` — One render-ready parameter of a wrapper method.
  - class `Binding` — One raw op backing a (possibly multi-binding) wrapper method.
  - class `MethodView` — One typed wrapper method on an object (``client.<object>.<name>(...)``).
  - class `ObjectView` — A typed wrapper class for one classified object.
  - `build_wrapper_context(inv, overrides, discovered, docs)` — Build the object-granular wrapper render context for a built SDK.
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

- Specs: `docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md`,
  `docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md`
- Decisions: (added in the scale increment) `decisions.md`
- Rules: `CLAUDE.md`
