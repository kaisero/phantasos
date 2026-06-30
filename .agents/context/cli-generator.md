# cli-generator

Validated against 8ab9ccf on 2026-06-25 · Purpose: how `phantasos cli build` turns a BUILT SDK into a vendored, scaffolded Typer + Rich CLI project.

## Purpose & responsibilities

`generator/cli/` owns the most complex build in the repo: it imports a product's
already-built Python SDK, introspects its facade resources into a typed operation
inventory, classifies those operations into a command tree (the CLI IR), and
statically renders a Typer + Rich CLI project around it (per-resource command
modules + a config/history/diagnostics runtime). The product's `cli.yml` supplies
only the declarative *deltas* the auto-classifier cannot infer (non-CRUD remaps,
union variants, hidden ops, table columns, query defaults). The emitted
`<package>_cli/_generated/` package is a pure build artifact — rebuilt on every
`cli build`; all hand-owned code lives in `main.py`, `hooks.py`, and `custom/`.

## How it works

Host commands live in `phantasos/cli.py` (`cli_discover`, `cli_build`) — NOT in
this package. Both route through `classify.build_ir(package, sdk_path, cfg)`, which
detects a **federated** SDK (one exposing a `_SUBPACKAGES` dict — snake slug →
sub-facade `Client` — on its top-level package, the same seam the SDK-docs
`gen_ref_pages` keys off). Single-spec SDKs (no `_SUBPACKAGES`) take the unchanged
single-pass path below. A federated SDK runs the introspect→classify stages **per
sub** (`f"{package}.{slug}"`, each against its own delta from `cfg.subpackages[slug]`
in the federated cli.yml) and `merge_federated_irs` folds the results into ONE
`CliIR`: every `Command` stamped with its `subpackage` (the snake slug), unmapped ops
slug-prefixed, models merged under slug-qualified keys (`f"{slug}.{ClassName}"`, refs
rewritten in lockstep), and `facade_module` set to the top-level package (which
exposes the composing `Client`, not a sub-facade). A cross-sub object-name collision
is a hard build error, as is a federated non-CRUD op left with no cli.yml mapping
(fail-loud, federated-only).

**Enrollment allowlist (federated):** `cfg.subpackages` doubles as the enrollment
allowlist — a *non-empty* map builds CLI ONLY for its listed subs (∩ `_SUBPACKAGES`,
iterated in `_SUBPACKAGES` order); a sub not listed is skipped entirely, so a
federated CLI can ship a thin slice (e.g. prisma-access P0 = `objects` + `incidents`)
without mapping every other sub's non-CRUD ops, then widen to the full surface — P1
enrolls all 12 prisma-access subs, each listed sub mapping its non-CRUD ops into the
`request` namespace (32 across config/identity/network/posture/security/ztna) so the
fail-loud build stays green. An *empty/absent* map enrolls ALL
subs (a config-less federated build stays backward-compatible). A sub listed but
absent from `_SUBPACKAGES` is a typo → hard error. Region/tenant connection headers
are NOT in cli.yml: they live once in the product's sdk.yml `default_headers` and
flow into the CLI build via `load_product`.
They wire the three pipeline stages together:

1. **Introspect** — The pure introspection and classification helpers
   (`introspect`, `classify_name`, `detect_id_param`, the `OperationInventory`
   types) now live in the stage-agnostic `generator/opmodel/` package, shared with
   the SDK wrapper generator. `generator/cli/introspect.py` and
   `generator/cli/inventory.py` are thin backward-compatibility shims that
   re-export from there. `introspect(package, sdk_path)` imports the built SDK
   (briefly on `sys.path` via the shared `opmodel/_pathutil.on_sys_path` context
   manager — the single guard reused by `introspect`, `classify.cli_operations`,
   and `modelschema.build_model_registry`), reads `extras.facade._RESOURCES`, and
   walks each raw `*Api` class's public methods via reflection (signatures, type
   hints, docstrings, pydantic model fields). It produces an `OperationInventory` (`OperationInfo` / `ParamInfo` /
   `FieldInfo`), classifying each param as path / query / body and capturing the
   response model + list-envelope `items_field` for table columns. The
   `body_fields` map records oneOf-variant model fields. For a oneOf **list** item,
   `_item_fields` reports the union (superset) of the variant models' fields — not
   the wrapper scaffolding — so default and curated columns resolve against real
   variant fields (bare names, no `actual_instance.` prefix).
   `classify.cli_operations(package, sdk_path)` is the wrapper-rebased entry
   (default for `cli build`): it walks `extras.facade._WRAPPERS` (object attr →
   wrapper class + backing `*Api` attr) and each wrapper's `_bindings` (clean verb
   → list of raw-op dicts), emitting one `OperationInfo` PER BINDING keyed by the
   RAW `(api_resource, raw_method)`. Each record reuses the raw-method
   introspection verbatim — so the command tree still classifies off
   `api_resource.raw_method` and every `cli.yml` key resolves unchanged — and
   stamps three dispatch-routing fields onto it: `object_attr` (the
   `client.<object>` target → `Command.sdk_resource`), `clean_method` (the typed
   wrapper verb → `MethodBinding.sdk_method`), and `has_body` (so the body is
   sent under the wrapper method's `body` kwarg). When those fields are unset (the
   legacy `_RESOURCES` path), `build_cli_ir` falls back to the api attr + raw
   method, so both paths share one classifier.
2. **Classify** — `classify.build_cli_ir(inv, cfg)` in `classify.py` turns the
   inventory + `cli.yml` (`CliConfig`) into a `CliIR` plus a list of unmapped ops.
   Precedence: `cli.yml` `hide` > `request` > `override`/`variants` >
   `classify_name` prefix heuristic (`create_`/`patch_`/`update_`/`delete_`/`get_`/`list_`
   → verb + sub_verb + singularized kebab object). `patch_` and `update_` both map to
   the `update` verb but with distinct sub_verbs (`patch` vs `put`): a post-loop pass
   relaxes update body flags to optional ONLY when the command has a `patch` binding
   (PATCH is partial); a PUT-only `update` keeps the model's required body fields
   required (full-replace). It detects the id path param,
   builds path/body/query `Flag`s, resolves union variants to variant subcommands,
   and resolves per-OBJECT table columns (see the comment block in `classify.py` —
   columns resolve per object via the show command's item model, never per
   command, because write ops return divergent response models).
   It also flags `Command.get_by_id_only` — a `show` whose only binding is a single
   get-by-id (no list endpoint) — so the runtime can emit a precise "no list
   operation" error instead of the generic no-match message.
   `build_cli_ir` is an **orchestrator over named stages**, not a monolith: it runs
   `_validate_defaults` (cli.yml `defaults` sanity), the per-op `_emit_command`
   (promoted from the old inner `_emit` closure), then three post-loop passes —
   `_relax_patch_body_requiredness` (the PATCH-vs-PUT body relaxation above),
   `_flag_get_by_id_only`, and `_resolve_columns` (per-object column resolution).
   Each stage is independently readable and testable; the refactor cut
   `build_cli_ir`'s cyclomatic complexity from F (53) to C (19) with no behaviour change.
3. **Render** — `render_cli.render_cli(ir, package, out_dir, *, env_prefix,
   distribution, auth)` in `render_cli.py` wipes/re-emits `_generated/` from Jinja
   templates: the runtime modules, one command module per SDK resource, the
   `app.py` factory, a typed copy of the IR models (`spec.py`, copied from
   `ir.py`) and `ir.json`. `render_cli` is itself **data-driven** — the fixed
   one-shot renders are a `_GENERATED` table of `(template, output-path)` pairs
   looped over, and the variable work is factored into named helpers: `_enrich_ir`
   (the auth/errors IR enrichment described next), `_render_commands` (the
   per-resource command modules), and `_render_docs` (the optional docs site). The
   extraction cut `render_cli`'s cyclomatic complexity from E (32) to C (15) with
   no behaviour change. The `auth` parameter is the product's resolved auth
   component (`loaded.auth`, passed by `cli_build`); when present, its
   `credential_fields()` enrich a `model_copy` of the IR (`ir.credential_fields`)
   BEFORE any template render or the `ir.json` write, so templates, `spec.py`, and
   the serialized IR all see the same enriched copy. That field gates the
   auth-only emissions (`environment_commands.py`, the `environment` app, the
   credential pre-flight). The `errors` parameter (`loaded.errors`) is enriched the
   same way: its `error_fields()` populates `ir.error_envelope`, so the emitted
   `diagnostics._error_headline` is config-driven (peel `wrappers` → `error_field` →
   `errors_field` → product-AGNOSTIC `fallback_keys`) and carries NO product-specific
   error keys; with no error component the default generic envelope applies. The
   `default_headers` parameter (the product's `ProductConfig.default_headers`,
   region/tenant `HeaderSpec`s) is enriched the same way into
   `ir.connection_fields`: non-secret "environment fields" that ride the SAME
   named-environment seams as credentials (prompted/stored per environment,
   exported to their `env` var BEFORE the SDK client is built, overridable by a
   per-field global `--<field>` flag). A `has_env` ctx flag (`credential_fields or
   connection_fields`) gates the SHARED environment infrastructure so it is emitted
   whenever EITHER is present; `connection_views` carries each header's derived flag
   name (`field.name.split("-")[-1].lower()`, colliding pairs fall back to the full
   kebab header). It
   `ruff`-formats only the files it wrote, then emits
   the hand-owned files (`main.py`, `hooks.py`, `custom/__init__.py`) ONCE (never
   overwritten on rebuild). `cli_build` then lays down the project scaffold via
   the sibling `scaffold` module, using
   `scaffold_context.build_cli_scaffold_context()` (the SDK product context
   overridden for the CLI) and `cli_overrides/` as the override tree. When
   `cli.yml` carries a `docs:` block, `render_cli` ALSO emits a documentation
   site (`docs/` + `mkdocs.yml`) — see *Generated documentation site* below.

`discover.py` (`render_table`, `render_stub`) renders the human-readable
classification table and a `cli.yml` stub for `cli discover`. `columns.py`
(`default_columns`, `resolve_columns`) derives/validates table columns against the
row model (JMESPath, snake_case keys). `cliconfig.py` is the `cli.yml` model +
`load_cli_config`.

## The IR (`ir.py`)

`CliIR` = `sdk_package` + `sdk_version` + `facade_module` + a flat list of
`Command`s. A `Command` is a `verb:object[:variant_or_action]` node carrying its
`path_params` / `body_flags` / `query_flags` (`Flag`s), resolved `columns`, and a
list of `MethodBinding`s (candidate SDK methods; runtime picks one by the args
present). `Flag.cli_default` (a `cli.yml`-injected value that IS rendered) is
distinct from `Flag.default` (the SDK/model default, NEVER rendered — body flags
stay None so PATCH won't silently resend model defaults). The IR is serialized to
`_generated/ir.json` and reloaded at CLI runtime against the emitted `spec.py`.

The classification-vocabulary aliases `Verb` / `SubVerb` / `FlagKind` (the
`Literal` sets `ir.py` annotates its models with) are **canonically defined in
`opmodel/vocab.py`** — the base layer — so the shared `opmodel` package never has
to import UP into `cli` (restoring an acyclic `opmodel -> {sdk, cli}` layering).
`ir.py` keeps a **byte-identical copy** of those three aliases on purpose: its
source is copied VERBATIM into each emitted CLI as `_generated/spec.py`, a
standalone package with no `opmodel` to import from. The two definitions MUST stay
in sync — their values serialize into the frozen `ir.json` / `spec.py` contract.

The IR also carries a **deduped nested-schema model registry** for complex
(`json`-kind) body flags: `CliIR.models: dict[str, ModelSchema]` (each body
model emitted once, keyed by its class name) and `Flag.model_ref` (a `json`
flag's pointer into that registry). A `ModelSchema` is a `list[ModelField]`
(+ `is_oneof`); a `ModelField` records `name`/`alias` (wire key), `py_type`,
`kind`, `required`, `description`, `enum_values`, `default`/`example`, plus the
edges that keep the registry normalized — `model_ref` (a nested known model) and
`variant_refs` (a oneOf/union's variant keys, rendered as tabs). See *Nested
body-model registry* below. Spec: `docs/specs/2026-06-22-cli-flag-schema-ir-and-docs-design.md`.

## Nested body-model registry

Complex body fields (nested object / `list[Model]` / oneOf) used to collapse to
`str`/`TEXT` with an empty help and a `'{}'` example: the full schema survived
SDK introspection (`FieldInfo.annotation`) but was dropped at
`fields_to_flags` (the `json` branch sets `py_type="str"`), and the `Flag` IR had
nowhere to hold nested structure. The registry closes that gap end to end.

- **`modelschema.py` = live models → registry.** This is the one seam that walks
  the *live* SDK body classes (already imported by the wrapper-rebased
  `cli_operations`). `build_model_registry(package, sdk_path, inv)` collects every
  body-model root in the inventory and `registry_from_models(roots)` recurses each
  via the now-public opmodel primitives (`field_kind`/`unwrap_optional`/
  `enum_values`/`scalar_type`/`union_members`, walking `cls.model_fields`),
  emitting one `ModelSchema` per reachable class into a `dict` keyed by class name. Recursion is **emit-once**
  (a model already in the registry is referenced, not re-expanded) so reuse-heavy,
  deep prisma-browser schemas stay bounded and cycle-proof (mirrors pydantic
  `$defs`/`$ref`). The recursion runs in the CLI layer to keep the SDK-shared
  `FieldInfo`/`OperationInfo` types unpolluted (separation of duty); opmodel only
  exposes its walking primitives. Each `ModelSchema` also carries the model's own
  schema-level `description`: `_model_doc(cls)` reads the class docstring that
  openapi-generator writes from the OpenAPI component `description` (and drops it
  when it is just the bare class name — that is openapi-generator's marker for a
  description-less schema). `build_cli_ir(inv, cfg, models)` threads the
  built registry onto `CliIR.models` and stamps each `json` flag's `model_ref`.

- **`ir.py` `synth_skeleton(models, model_name, *, full)` = registry → JSON
  skeleton.** A self-contained (stdlib + pydantic only) synthesizer that turns a
  registry entry into a copy-&-fill JSON body. `full=True` emits every field
  including optionals (the docs "Full body"); `full=False` emits a required-only
  **minimal** skeleton with a non-empty guarantee — an all-optional model still
  emits one representative (first-declared) field recursively, so the example is a
  valid minimal body rather than an API-rejected `{}`. Field values follow
  `example > default > type-synth`; wire/alias (camelCase) keys are used. Because
  `spec.py` is the verbatim copy of `ir.py` (the `render_cli.py` `ir.py`→`spec.py`
  mechanism), the synthesizer ships to the runtime unchanged — every surface is
  byte-identical by construction.

These two halves feed **four surfaces**, all off the single registry:

1. **`--help` annotation** (`commands.py.jinja` / `examples.py`) — a `json` flag's
   help becomes `{help} [json: <Model>] e.g. {compact-minimal-skeleton}`
   (single-line, `full=False`), replacing the old empty help + `'{}'`.
2. **Docs one-line invocation** (`examples.py:example_value`) — the same compact
   minimal skeleton replaces `'{}'` in the quickstart/reference invocation.
3. **Docs progressive disclosure** (`reference_object.md.jinja`) — each complex
   flag row is followed by a collapsed `pymdownx.details` block (`??? note`) with
   that model's field table; sub-models nest (collapsed, 4-space-indented),
   oneOf fields render as `pymdownx.tabbed` tabs, and each command gets a
   collapsed `??? example "Full body (copy & fill)"` (`full=True`) skeleton. New
   `mkdocs.yml` extensions: `pymdownx.details`, `attr_list`, `pymdownx.tabbed`.
   In `docs.py`, a nested-model body flag with an empty help cell **falls back to
   the registry model's `description`**: both `_flag_row` and the recursive
   `_schema_rows` resolve an empty cell via `_ref_description(models, ref)` (which
   reads `ModelSchema.description`), so a flag like `--microsoft` shows the model's
   schema-level prose in the Body table instead of a blank. The Body-table **Type
   cell links to that flag's schema disclosure block**: when a flag has a schema,
   `_flag_row` stamps a page-unique `type_anchor` slug from `_anchor(key, flag)`
   (command key + flag name, so the same flag under two commands gets distinct
   anchors), the template renders the Type cell as `[`<Model>`](#<type_anchor>)`,
   and emits a matching invisible `<a id="<type_anchor>"></a>` on the line ABOVE the
   `??? note` disclosure (the blank line between the anchor and `??? note` is
   load-bearing — it keeps `pymdownx.details` from swallowing the admonition).
4. **Runtime input-error example** (`runtime.py.jinja`) — the corrective JSON in a
   bad-input error is registry-driven and **debug-adaptive**: it shows the FULL
   skeleton when debug logging is active (`log_level_int(...) <= 10`), else the
   minimal-non-empty one. Anonymous json (no `model_ref`) keeps the
   `{"key": "value"}` fallback.

> Known minor: a `json` field whose annotation can't be resolved to a registry
> model (no `model_ref`/`variant_refs`) shows its raw `py_type` in the docs Type
> cell — for some prisma-browser fields that is a long `typing.Annotated[…] | None`
> with an unescaped `|`. It is cosmetic only: the cell is backtick-wrapped, so the
> markdown table parser doesn't split on the `|` (the rendered `<tr>` keeps 4
> `<td>`s and `mkdocs build --strict` passes); it's just noisy, not broken.

## Templates & overrides

- `templates/_generated/*.jinja` — the rebuilt-every-time package: `app.py`
  (Typer factory wiring verb sub-apps + `config`/`show cli` meta-apps),
  `commands.py` (one rendered module per SDK resource), `runtime.py` (load IR,
  dispatch to the SDK method, coerce flags, render), `config.py` +
  `default_config.yml`, `config_commands.py`, `history.py`, `diagnostics.py`,
  `output.py`. Generated from the IR — never hand-edited in an emitted project.
- `templates/custom/__init__.py.jinja` + top-level `main.py.jinja`,
  `hooks.py.jinja` — hand-owned scaffolding emitted ONCE (`_HANDOWNED` in
  `render_cli.py`); a rebuild leaves them untouched so users can customise the
  entrypoint, register `custom/` commands, and implement runtime hooks.
- `cli_overrides/` — NOT generator code: the per-product scaffold override tree
  (a `README.md.jinja` + `tests/` Jinja templates: `conftest`, `test_cli_smoke`,
  `test_config`) that `scaffold.render_scaffold` layers over the built-in SDK
  scaffold, mirroring `products/<name>/overrides/` for SDKs.

## N-level Typer nesting

`templates/_generated/app.py.jinja` emits the Typer factory. For a **single-spec** build the output is byte-identical to the pre-federation factory — the template's `{% else %}` branch is untouched. For a **federated** build the template gates on a `federated` context flag and produces a deeper command hierarchy: **verb → sub-package → object** (so `prisma-access show objects address` maps cleanly), with a fourth level for `request <sub> <object> <action>` and for oneOf-variant commands.

Sub-package command names are rendered as **kebab-case** (`network_services` → `network-services`) while `Command.subpackage` stays the original snake slug — lookup by `cmd.subpackage` is always unambiguous. Intermediate Typer sub-apps (one per `(verb, *path[:depth])` tuple) are created on demand and keyed into a dict; the template registers each intermediate app exactly once regardless of how many objects share the same verb/sub prefix.

## Runtime federation dispatch

`templates/_generated/runtime.py.jinja` is the dispatch core. When `cmd.subpackage` is set (a federated command), every seam that needs to know the concrete sub-package resolves off that slug rather than the top-level package:

- `_models` → `{pkg}.{sub}.models` (response coercion and type lookups)
- `_accepted_params` → `{pkg}.{sub}.extras.facade._WRAPPERS` (dry-run and param filtering)
- `_sdk_exc` → `{pkg}._runtime.exceptions` for federated SDKs (runtime lives at the top level); `{pkg}.exceptions` for single-spec SDKs
- `_dry_run` delegates to the sub wrapper's `_serialize` method

Dispatch itself is two-level: `getattr(getattr(client, cmd.subpackage), cmd.sdk_resource)` — first resolve the sub-package attribute on the composing `Client`, then the resource attribute on the sub-facade's client. Single-spec commands (`cmd.subpackage` unset) fall through to the unchanged `getattr(client, cmd.sdk_resource)` path.

The command-aware connection-field pre-flight (`_preflight_connection`) is already documented under *Emitted features → Connection headers*.

## Layered config of emitted CLIs

Each generated CLI resolves every user-facing setting through one layered flow:
packaged defaults ← `~/.{distribution}/config.yml` ← `.env`/env ← per-invocation
flags. The mechanics are emitted from `templates/_generated/config.py.jinja`
(frozen pydantic section models + `_ENV_MAP` + cached `load_config()` +
`effective_dict()`) and `default_config.yml.jinja` (commented defaults that MUST
mirror the model defaults). Consumers read via `_config.get().<section>.<key>`.
Current sections: `pager`, `output`, `history`, `logging` (`level`, `file`).
`config set <key> <value>` / `config unset <key>` write/remove options in
`config.yml` (type-coerced; unknown keys or invalid values exit `2`; writing
strips the commented template — `config init --force` restores it). To ADD an
option, follow the recipe in `CLAUDE.md` → "Adding a CLI configuration option
(generated CLIs)" — it owns the step-by-step rules (do not duplicate them here).

## How `cli.yml` feeds the build

`products/<name>/cli.yml` (model: `CliConfig` in `cliconfig.py`) supplies only
deltas over the always-on classifier: `project` (scaffold metadata),
`variants` (REQUIRED path-enum → variant-model map for undiscriminated oneOf
bodies, e.g. `set application custom`), `request` (non-CRUD ops → the `request`
namespace), `override` (fix verb/object), `hide` (exclude ops), `columns`
(per-object table columns; bare string = header==path, else header/path JMESPath),
and `defaults` (per-op query-param defaults injected as rendered flag defaults —
e.g. the prisma-browser sort+order that makes cursor pagination work). Unknown op
keys / param names / objects fail the build loudly.

## Emitted features

- **History** — real API calls append to a JSONL file; viewed via
  `show cli history` (`cli_commands.py.jinja` + `history.py.jinja`). Spec:
  `docs/specs/2026-06-12-cli-history-design.md`.
- **Pager + user config** — `config` meta-commands + the layered config + pager.
  Spec: `docs/specs/2026-06-11-cli-user-config-pager-design.md`.
- **Diagnostics / error UX** — unified Rich stderr diagnostics (`diagnostics.py`).
  Spec: `docs/specs/2026-06-12-cli-diagnostics-and-error-ux-design.md`.
- **Output rendering** — JSON (default) / table / YAML, with Rich coloring + pager
  (`output.py`). Spec: `docs/specs/2026-06-13-cli-yaml-rich-coloring-design.md`.
- **Common options panel** — shared `--output`/`--pager`/`--quiet` etc. help
  panel. Spec: `docs/specs/2026-06-11-cli-common-options-panel-design.md`.
- **Named environments** (auth OR connection-header CLIs — anything with
  `has_env`) — credentials stored in `~/.{distribution}/environments.yml`
  (`environments:` + `default_environment:`, `${VAR}` refs expanded at read time).
  Top-level `environment` command group (`create`/`activate`/`show`/`delete`;
  `show` never prints secret values but DOES show non-secret connection values,
  `delete` --force-gates the active env, first create auto-activates; `create`'s
  per-credential options are built from `ir.credential_fields`). Active env
  resolves `-e/--environment` flag > `{PREFIX}_ENVIRONMENT` env var >
  `default_environment`; per-field credential env vars still override the env.
  Helpers in the emitted `config.py` (`resolve_environment`, `default_environment`)
  + `runtime.py` (`select_environment`); commands in `environment_commands.py.jinja`.
- **Connection headers** (region/tenant; `ir.connection_fields`) — non-secret
  environment fields stored per environment under their derived flag-name key and
  exported to their `env` var in `runtime._client` BEFORE the SDK client is built
  (the SDK reads e.g. `PANW_REGION` from the environment — no header kwarg). Each
  emits one global `--<field>` flag (Connection help-panel) layered
  `--flag > {field.env} env var > active-environment value`. **Per-command collision
  filter** (`render_cli._command_view`): a global connection flag is omitted from the
  signature AND `set_connection_overrides` call of any command whose own path/body/query
  field already renders that `py_name` — declaring the parameter twice would be a
  `SyntaxError` (e.g. prisma-access `remote_network`'s `region` body field vs the
  X-PANW-Region flag). The header value still flows from env / active-env / config and
  the pre-flight still enforces it; only the redundant per-command flag is dropped, and
  non-colliding connection flags on the same command are untouched. The `--flag` value is
  threaded through `runtime.set_connection_overrides` (a per-command contextvar);
  `config.resolve_connection` resolves the active-env value; the per-field env-var
  baked list is `config._CONN_FIELDS`. Single-spec CLIs (no `default_headers`) emit
  none of this. Command-aware pre-flight (`_preflight_connection` in `runtime.py`): each `ConnectionField` carries a `required_for` list of sub-package slugs; the pre-flight exits 2 for any command whose `cmd.subpackage` appears in that list (or whose field is globally `required: true`), naming the missing env var and why; commands in other sub-packages pass through unchecked (objects CRUD runs region-unset while a sub that declares the header required would block).
- **`which <object>`** (federated CLIs only; `cli_commands.py.jinja`) — an emitted top-level command that looks up a named object in `ir.json` and prints its sub-package + supported verbs; `difflib.get_close_matches` produces `did-you-mean` suggestions for unknown names (exit 1 on miss). Wired into the generated `app.py` in the "CLI" panel when the IR is federated.
- **Structured logging** — a rotating JSON-Lines log at
  `~/.{distribution}/logs/{distribution}.jsonl` (`0o600`, gzip-rotated);
  `warnings` (incl. the SDK lenient-enum pass-through) and CLI diagnostics go to
  it instead of the terminal, with a terse stderr summary at exit. New `logging`
  config section (above). Emitted `logging_setup.py.jinja`. See CHANGELOG
  Unreleased for the exact behavior (no dedicated spec).
- **Credential pre-flight** (auth CLIs) — `runtime.py` checks
  `ir.credential_fields` before the first request: missing REQUIRED credentials
  fail cleanly (exit `2`) naming the variables (and active env, if any) and
  pointing at `environment create` / the env vars, instead of a raw traceback; a
  genuine auth failure with credentials present exits `1` (`--verbose` keeps the
  traceback). See CHANGELOG Unreleased.

## Generated documentation site

Opt-in per product via a `docs:` block in `cli.yml` (`CliDocsConfig`:
`showcase_object` [required], `showcase_variant`, `site_name`, `examples`). When
present, `render_cli` emits a standalone MkDocs-Material site into the CLI project
(`docs/` + `mkdocs.yml`), built strict by the `cli-docs` nox gate.

It is **IR-driven and generate-time**: the command reference is a pure function of
the `CliIR`, rendered to concrete markdown at `cli build`. It deliberately does NOT
use mkdocstrings / mkdocs-gen-files / literate-nav like the per-SDK docs site (those
autodoc Python; the CLI's user surface is the command tree). See
`docs/adr/0001-cli-docs-ir-driven-generate-time.md`.

- `docs.py` — `build_cli_docs_context(ir, docs, *, distribution, site_name,
  repo_url, description)` shapes the render context (per-object command groups, the
  `showcase` object/variant, guide-gating flags, credentials, the `error_envelope`
  sub-dict). It validates `showcase_object` against the IR objects (fail-loud);
  `CONTEXT_KEYS` pins the producer/template contract.
- `examples.py` — synthesizes required-only invocation examples (`render_invocation`)
  + a per-flag value strategy (`example_value`). Deliberately NOT shared with
  `sdk/examples.py` (different output: shell vs Python constructor); it DOES share
  `flags.py`.
- `flags.py` — `dedupe_flags`/`query_panel`/`leaf`, imported by BOTH `render_cli`
  (emitted command modules) and `docs.py` (the reference), so the command
  reference's flag set/grouping can never drift from the emitted `--help` (a drift
  test in `tests/cli/test_docs_context.py` locks it).
- `templates/docs/**.jinja` — `index` (verb-model explainer), `quickstart`
  (showcase-driven, honoring `showcase_variant`), per-object `reference_object`,
  four guides (output/errors always; authentication gated on credentials,
  pagination on any paginated command), and `mkdocs.yml` with an explicit
  IR-generated `nav`.
- Scaffold seam: `build_cli_scaffold_context` sets `cli_docs = (cli.yml docs is not
  None)` while keeping the SDK `has_docs` flag False — so the shared SDK-flavored
  docs templates never fire for a CLI. The shared `pyproject.toml` / `noxfile.py` /
  Pages-workflow / README templates gain a minimal `cli_docs` branch (CLI docs
  dependency group = `mkdocs-material` only).
- Gate: `nox -s cli-docs` (per-product, enrolled in `nox.toml [cli-docs]`) builds
  each enrolled SDK + CLI and runs `mkdocs build --strict` + content asserts;
  offline behavior is covered by `tests/cli/` against the `fakesdk` fixture.

## Build / run pointers

- Inspect classification: `phantasos cli discover <name>` (`--write-stub` writes
  `products/<name>/cli.yml.stub`). Needs the SDK built and importable.
- Emit the CLI project: `phantasos cli build <name>` (writes a sibling
  `<sdk-dist>-cli/` project next to the SDK).
- Tests (`ls tests | grep -i cli`): the unit seams (`test_cli_classify.py`,
  `test_cli_columns.py`, `test_cli_command.py`, `test_cli_discover.py`,
  `test_cli_introspect.py`, `test_cli_operations.py`, `test_cli_ir.py`,
  `test_cli_modelschema.py`, `test_cli_skeleton.py`, `test_cli_render.py`,
  `test_cli_scaffold.py`) plus the host-CLI dispatch (`test_cli.py`). The big
  `test_cli_emitted.py` was **split per-seam** into `test_cli_emitted_config.py`,
  `…_environments.py`, `…_history.py`, `…_logging.py`, `…_runtime.py` (a slim
  `test_cli_emitted.py` / `test_cli_emitted_real.py` remain); the shared `emitted`
  fixture and the `render_and_import` helper they all build on now live in
  `tests/conftest.py`. Behavioral tests run through the emitted package; config is
  cached at command-module import (set HOME/env before import;
  `load_config.cache_clear()` after mutating env). Offline CLI-docs tests live
  under `tests/cli/` (against the `fakesdk` fixture); the opmodel split has its own
  `test_opmodel_classify.py` / `test_opmodel_pathutil.py`. Slow OAG-jar builds are
  tagged with the `slow` marker (deselect with `-m "not slow"`).

## Module map

<!-- GENERATED:module-map -->
- `classify.py` — Deterministic classification of SDK methods into the CLI command tree.
- `cliconfig.py` — The per-product cli.yml model — declarative deltas only; the classifier always runs.
- `columns.py` — Table-column resolution: model-derived defaults + cli.yml validation.
- `discover.py` — Render the classification table and a cli.yml stub from a CliIR.
- `docs.py` — Build the CLI docs render context from the resolved CliIR (IR-driven, generate-time).
- `examples.py` — Synthesize illustrative CLI invocations from the resolved command IR.
- `flags.py` — Shared flag-grouping helpers for the CLI generator.
- `introspect.py` — Backward-compatibility shim: introspect now lives in generator.opmodel.introspect.
- `inventory.py` — Backward-compatibility shim: inventory types now live in generator.opmodel.inventory.
- `ir.py` — The CLI intermediate representation: the fully-resolved command tree.
- `modelschema.py` — Walk live SDK body models into the deduped CliIR model registry.
- `render_cli.py` — Emit a Typer CLI project from a CliIR (static codegen via Jinja).
- `scaffold_context.py` — Build the scaffold context for an emitted CLI project (reuses the SDK scaffold).
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
- `classify.py`
  - `classify_name(method)` — CLI-local prefix classification: ADDS the PUT `update_*` -> (update, put) case.
  - `cli_operations(package, sdk_path, registry_attr)` — Inventory built from the SDK's typed wrappers (`_WRAPPERS`/`_bindings`).
  - `select_method_for_verb(methods)` — Return the preferred method when multiple share the same verb.
  - `fields_to_flags(fields, schema)`
  - class `ResolvedVariant`
  - `resolve_variants(op, vmap)` — Map a method's path-enum values to variant models via cli.yml (the SDK oneOf
  - `build_cli_ir(inv, cfg, models)`
  - `merge_federated_irs(package, sdk_version, subs)` — Merge per-sub CliIRs into ONE federated CliIR.
  - `build_ir(package, sdk_path, cfg)` — Build the CliIR for a single- OR federated-spec SDK.
- `cliconfig.py`
  - class `RequestMapping`
  - class `Override`
  - class `VariantMap`
  - class `ColumnEntry`
  - class `CustomPointer`
  - class `CliDocsConfig` — Opt-in CLI documentation generation (cli.yml `docs:` block).
  - class `CliConfig`
  - `load_cli_config(path)` — Load cli.yml; return an empty CliConfig if the file is absent.
- `columns.py`
  - `default_columns(fields)` — Preferred names first, then remaining scalar/enum fields in declaration
  - `resolve_columns(entries, fields, obj)` — Normalize cli.yml column entries; raise ValueError (-> build failure) on
- `discover.py`
  - `render_table(ir, unmapped)`
  - `render_stub(ir, unmapped)` — A cli.yml stub: TODO entries for unmapped ops. CRUD is auto-classified, so the
- `docs.py`
  - `build_cli_docs_context(ir, docs, distribution, site_name, env_prefix, repo_url, description)`
- `examples.py`
  - `example_value(flag, models)` — A shell-safe example value token for one flag.
  - `render_invocation(command, distribution, override, models)` — A one-line invocation example (required flags only) or the verbatim override.
- `flags.py`
  - `query_panel(f)`
  - `leaf(c)` — The third command segment: a oneOf variant OR a request action (mutually
  - `dedupe_flags(c)` — Return (body, query) flags deduped against path params (path wins), then
- `ir.py`
  - class `CredentialField` — Describes one credential field exposed by an auth component.
  - class `ConnectionField` — Describes one request header sourced from an env var (e.g. region/tenant).
  - class `ErrorEnvelope` — Config-driven description of a product's error body, threaded onto the IR so
  - class `Flag`
  - class `MethodBinding`
  - class `ColumnSpec` — One table column: a header + a JMESPath evaluated against each row dict
  - class `Command`
  - class `ModelField` — One field of a body model, captured for the CLI payload-helper skeleton.
  - class `ModelSchema` — A body model's field surface, stored deduped under a key in `CliIR.models`.
  - class `CliIR`
  - `synth_skeleton(models, model_name, full)` — Synthesize a JSON skeleton for ``model_name`` from the registry.
- `modelschema.py`
  - `registry_from_models(roots)` — Deduped registry of every model reachable from ``roots``.
  - `build_model_registry(package, sdk_path, inv)`
- `render_cli.py`
  - `cli_overrides_dir()`
  - `render_cli(ir, package, out_dir, env_prefix, distribution, auth, errors, default_headers, docs, docs_site_name, docs_repo_url, docs_description)`
- `scaffold_context.py`
  - `build_cli_scaffold_context(loaded, ir, cli_cfg)` — CLI scaffold context = the SDK product context, overridden for the CLI.
<!-- /GENERATED:api -->

## Gotchas / invariants

- **The emitted `_generated/` package is a pure artifact** — wiped and re-rendered
  every `cli build`. Only `main.py`, `hooks.py`, `custom/` (the `_HANDOWNED` set)
  survive a rebuild; never hand-edit `_generated/`.
- **The classifier always runs.** `cli.yml` only supplies deltas — it never
  replaces classification. A typo in a `cli.yml` op key / param / object /
  JMESPath / variant fails the build rather than being silently ignored.
- **Columns resolve per OBJECT, not per command** (see the long comment in
  `classify.py`): write ops return divergent response models, so columns derive
  from the object's show command item model and attach to every command of that
  object; a JMESPath miss renders an empty cell.
- **Enum flags stay permissive** (`str` + completer choices, never a validating
  Enum) because the SDK uses `LenientStrEnum` and unknown server values must pass
  through. Scalar flags get their real type so Typer validates; bool flags render
  as value-taking `str` and coerce at runtime.
- **`object: cli` is reserved** for meta-commands (`show cli history`);
  `render_cli` rejects an IR object named `cli` — rename via a `cli.yml` override.
- **The `request` namespace** maps non-CRUD actions; some are reserved in
  `cli.yml` ahead of being emitted (the build skips them cleanly, no "unmapped").
- **Some phase-2 gaps are explicit TODOs in code**: `dict` / `list[Model]`
  request bodies are not yet introspected (`introspect.py`), and
  `select_method_for_verb` is reserved but not yet wired into `build_cli_ir`.
- **`get_by_id_only`** marks a `show` command backed solely by a get-by-id
  operation (no list binding; the get requires exactly the id). `runtime._pick_binding`
  uses it to print `'show <object>' has no list operation` + an `--id` hint when no
  binding matches, rather than the generic no-match diagnostic. Computed strictly
  (`requires == [id]`), so a `show` whose get also needs a discriminator is not flagged.
- **`show` get-vs-list dispatch.** On the wrapper surface a `show` command binds
  BOTH the object wrapper's `.get` and `.list` methods (two separate `MethodBinding`
  entries). The runtime dispatches between them based on whether `--id` is present:
  `--id` present → `.get(...)` (single-item fetch); otherwise → `.list(...)` (with
  any filter flags forwarded). Flags like `--name`/`--type`/`--folder` are NOT
  get-triggers — they are query filters passed to whichever branch is selected. The
  `--all` flag maps to `all_pages=True` on the `.list` call; the wrapper's
  `list(all_pages=True)` handles pagination internally and returns a full-envelope
  response so the table renderer is unchanged.
- **CLI dispatches through wrappers, not raw `*Api`.** The runtime calls
  `client.<object>.<clean_method>(...)` (the typed wrapper verb), never a raw
  `*Api` method directly. The dry-run seam is `resource._serialize(verb, **kwargs)`
  on the wrapper; HTTP capture wraps `client.api_client.call_api` at the facade
  level. Raw `*Api` method names appear only inside `_bindings` — they are not
  visible to the CLI runtime.

## See also

- Specs: `docs/specs/2026-06-09-cli-generator-design.md` (design),
  `docs/specs/2026-06-19-cli-on-clean-resource-wrapper-design.md` (wrapper surface
  + CLI-on-wrappers), plus the WP specs listed under *Emitted features*.
- Recipe: `CLAUDE.md` → "Adding a CLI configuration option (generated CLIs)".
- Adjacent docs: `sdk-generator.md` (the SDK this consumes, incl. `generator/opmodel/`),
  `product-config.md` (`productconfig.py` loader, incl. the `operations:` override block),
  `components.md` (component param models, incl. the facade two-pass render).
