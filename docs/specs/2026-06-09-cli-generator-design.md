# Design: CLI generator (`phantasos cli build`) — generate a Typer CLI from a built SDK

**Date:** 2026-06-09
**Status:** Draft for review
**Branch:** `cli-generator` (off `main`)

## Context & scope

phantasos generates self-contained Python SDKs from OpenAPI specs. This feature adds a
**generic, build-time CLI generator** that emits a Typer + Rich command-line interface from a
**built** SDK, by introspecting it. The first product is `prisma-browser-cli` (built from the
sibling `../prisma-browser-sdk/`); the generator is product-agnostic and reusable for `adem`
and future products via a per-product `cli.yml`.

The reference UX is [`cdot65/pan-scm-cli`](https://github.com/cdot65/pan-scm-cli): a verb-first
CRUD CLI. Unlike that hand-written CLI (~480 lines/resource), ours is generated from the SDK, so
commands map 1:1 to real SDK calls with no hand-maintained name-mapping layer.

Research + recon backing this design: `docs/research/2026-06-09-cli-generator.md`. Key verified
conclusions: prefer **static codegen via Jinja** over runtime/dynamic construction (also
required for `typer utils docs` + shell completion to work); mirror **pydantic-settings**
field→flag semantics; the cdot65 verb-first pattern is the model.

### In scope (v1)

The IR-centric generator and a working `prisma-browser-cli` with: verbs `create`/`update`/`delete`/
`show`/`request`/`load`/`backup`; full flag generation (scalars → typed flags, complex/union fields →
JSON-string flags); body-level union variants as subcommands; `cli.yml` overrides; config
(`config.yaml`) + `.env` auth; Rich/JSON/YAML output; static completion; errors-only logging;
generated command-reference markdown; a `--dry-run` flag on mutating verbs; tests.

### Deferred (designed-for, not built)

Full phantasos-grade scaffold parity with the SDK — all CI/CD workflows, **mkdocs site +
publishing**, release/audit/secrets/codeql, pre-commit, dotfiles, LICENSE/CHANGELOG — for
consistency, as a later enhancement. Also: dynamic (live-value) completion; dot-notation nested
flags; smart-upsert; whole-tenant `load`/`backup`; named profiles; a `--strict` build mode;
optional future move of SDK-gen to `generator/sdk/` for symmetry.

### Prerequisite logged separately

`docs/TODO.md` → "Harmonize ID path-parameter naming across generated SDKs". The CLI assumes a
canonical `--id`; harmonization happens in the SDK layer, not the CLI.

## Architecture: IR-centric pipeline

The generator lives in **`src/phantasos/generator/cli/`**. The existing top-level
`src/phantasos/cli.py` stays the entrypoint (`phantasos.cli:main`); it gains a `cli`
subcommand group that delegates into `phantasos.generator.cli`.

```
                         products/<product>/cli.yml  (deltas only)
                                       │
built SDK ─► introspect.py ─► classify.py ─► CliIR (typed) ─┬─► render.py (Jinja) ─► ../<product>-cli/
            OperationInventory   (+cli.yml merge)           └─► discover.py ─► report + cli.yml stub
```

- **`introspect.py`** — imports the built SDK; walks `extras/facade.py` `_RESOURCES`; for each
  `*Api` class enumerates public methods (excludes `*_with_http_info`, `*_without_preload_content`,
  `*_serialize`). Per method, extracts: each parameter's name, resolved type hint
  (`typing.get_type_hints(..., include_extras=True)`), `Annotated`/pydantic `Field` metadata,
  required/optional + default, the return type, and the docstring summary + description. For
  body-model params it recurses `model.model_fields`, and for union bodies records the candidate
  member models (the path-enum→variant mapping is applied later in `classify` via `cli.yml`).
  Output: a typed `OperationInventory`.
- **`classify.py`** — applies the classifier rules (below), merges `cli.yml` deltas, and
  produces the typed **`CliIR`** — the fully-resolved command tree. Pure and unit-testable.
- **`render.py`** — Jinja templates walk `CliIR` and emit standalone CLI source modules.
- **`discover.py`** — consumes the *same* `CliIR` to print a human report and write a `cli.yml`
  stub. Generation and discovery therefore cannot drift.

This mirrors phantasos's existing `productconfig → render` typed-model pattern.

## Command grammar & taxonomy

Verb-first: **`<verb> <object> [<variant>] [flags]`**

- **Verbs:** `create` (POST), `update` (PATCH), `delete` (DELETE), `show` (GET/list),
  `request` (non-CRUD actions), `load` (bulk import), `backup` (export).
  Deferred: full-replace `replace` verb (PUT when a PATCH also exists); `update`-fallback (PUT
  when no PATCH exists); `load`/`backup` depend on list[Model] body introspection (not yet built).
- **`request <object> <action>` (EMITTED — Phase 3b):** each `cli.yml` `request:` mapping
  `{object, action}` emits one command (verb `request`, a dedicated `Command.action` field — NOT
  the oneOf `variant`), bound to one SDK method, built from its id path param (if any) + body
  model. The emitter treats the leaf segment as `variant or action`; the runtime never inspects
  `action` (so the oneOf-discriminator path can't touch request commands).
- **Object** = facade resource **+ method noun**, so one facade resource splits into its real
  object types: `access_and_data_policy` → `access-and-data-rule`, `access-and-data-section`, …
- **Variant** = a body-level union member surfaced as a subcommand: `create application custom|private|…`,
  `update application custom|private|…`.
  **Important — the SDK's oneOf wrappers are *undiscriminated*** (verified: `CreateOrReplaceAppInput`
  has an empty `discriminator_value_class_map = {}` and deserializes by first-match trial). So
  variants are **not** auto-derivable from the body model. Instead, drive variant subcommands off
  the method's **path enum** (e.g. `type: ListApplicationsTypeParameter`), and map each path value
  to its variant model via a required `cli.yml` `variants:` entry (the SDK does not encode this
  mapping). Then flatten the chosen variant model's fields into flags. Note the cardinality can
  differ — applications expose **5 path values vs 4 body variants** (`catalog` has no create input),
  so the mapping is authored, not 1:1.
- **Single-binding writes:** each `create`/`update`/`delete` command has exactly one SDK binding.
  `--id` is required for `update` and `delete`. `create` enforces required body fields. PATCH body
  fields are all optional (partial update). Scalar flags carry real Python types.
- **`--dry-run`** on every mutating verb (`create`/`update`/`delete`/`load`/`request`): print the
  resolved SDK call + payload, do not execute.

### Classifier rules

| Method prefix | CLI verb |
|---|---|
| `create_` | `create` |
| `patch_` | `update` |
| `delete_` | `delete` |
| `get_`, `list_` | `show` |
| `update_` | hidden (deferred: future `replace`/`update`-fallback) |
| `bulk_create_`, `bulk_delete_` | hidden (deferred: future `load`/`backup`) |
| anything else | unmapped → needs `cli.yml` |

**Object noun:** strip the verb prefix and any trailing `_by_id` / `_by_type_and_id` /
`_by_type`, then singularize (`list_applications` → `application`). Methods sharing a noun group
under one object.

**Classification precedence (authoritative order):** `cli.yml hide`/skip-list → `cli.yml`
`override`/`request` → prefix heuristic. The skip/hide and explicit mappings are consulted
**before** prefix matching, so e.g. `update_security_positions` is treated as a reorder action
(`request`/skip) and never mis-classified as `update security-position`.

**ID parameter detection:** introspect must **detect** the id path-param per operation rather than
assume the literal name `id` (the SDK uses `id`, `device_group_id`, two-key `_by_type_and_id`,
etc.). Rule: the single required path param that is not a discriminator enum is the id; expose it
as `--id`. This lets v1 work *before* the SDK id-harmonization TODO lands. When an object has
multiple methods of the same verb (e.g. `delete_application_by_id` **and**
`delete_application_by_type_and_id`), the selection rule is: prefer the variant whose required
path params are all satisfied by the flags the user supplied; default to the fewest-params
variant, with `cli.yml override` as the tie-breaker.

**Unmapped policy: warn + skip.** Ops that don't classify (e.g. `suspend_*`, `archive_*`,
`force_reauth_*`, `revoke_*`, `publish_*`, `restore_*`, `resume_*`, `action_*`, `*_positions`,
sub-resource reads like `list_application_categories`) are listed in a build warning with guidance,
and omitted from the CLI until mapped in `cli.yml`. No `cli.yml` → CRUD-only + warnings. **Honest
caveat:** for prisma-browser ~14 ops are non-CRUD, so a no-`cli.yml` build is *substantially*
incomplete for this product — `cli.yml` authoring is expected, not optional.

### Flag generation (mirrors pydantic-settings)

- **Scalar / enum / simple-list** field → an individual typed flag (`--name`, `--enabled`,
  `--urls`). Enum fields carry `choices` to drive static completion, but the generated flag is
  **permissive**: emit a `str` param with a completer, **not** a validating Typer `Enum`. The SDK
  enums are `LenientStrEnum` (unknown values pass through by design), so the CLI must not be
  stricter than the SDK it wraps. Enum values may contain spaces/hyphens.
- **Nested object / array-of-objects / field-level union / dict** → a single JSON-string flag
  (`--extensions '[{...}]'`).
- An optional whole-body `--data <file|->` override (YAML/JSON) is always accepted.
- (Deferred: dot-notation per-field flags that override the JSON value.)

## The `CliIR` (typed data model)

Pydantic models in `generator/cli/ir.py`, roughly:

```python
class Flag(BaseModel):
    name: str                       # e.g. "--name"
    py_type: str                    # rendered annotation
    kind: Literal["scalar", "enum", "json", "file", "id"]
    required: bool
    default: Any | None
    help: str
    choices: list[str] | None       # for enum kind

# A user-facing command maps to ONE SDK method (single-binding writes).
class MethodBinding(BaseModel):
    sdk_method: str                 # e.g. "create_application"
    sub_verb: Literal["create", "patch", "get", "list", "delete"]
    requires: list[str]             # param names that must be present to select this binding
                                    # (e.g. ["id"] for patch/get-one; ["type"] for by_type)

class Command(BaseModel):
    verb: Literal["create", "update", "delete", "show", "request", "load", "backup"]
    object: str                     # kebab-case object noun
    variant: str | None             # union variant, if any
    key: str                        # canonical "verb:object[:variant]" — shared by templates,
                                    # factory exclude=, and ir.json
    sdk_resource: str               # facade attribute, e.g. "applications"
    bindings: list[MethodBinding]   # candidate SDK methods; runtime dispatch picks one by args
    path_params: list[Flag]         # ALL required path params (id + any discriminators, e.g. --type)
    body_flags: list[Flag]          # union across bindings
    query_flags: list[Flag]
    summary: str
    description: str
    paginated: bool                 # true if any binding is a list

class CliIR(BaseModel):
    sdk_package: str
    sdk_version: str                # built-SDK provenance, persisted to _generated/ir.json
    commands: list[Command]
```

`build_cli_ir` maps each operation to a single `Command` with one `MethodBinding`; `create`/
`update`/`delete` commands are independent (not aggregated by `--id`). `path_params` carries
**every** required path param (not just the id),
so the call is always reconstructable. `Command.variant` is resolved from the method's path enum
via `cli.yml` `variants:` (not from a body discriminator — the SDK's oneOf wrappers are
undiscriminated). The id `Flag` (kind `"id"`) is the detected required path param, not assumed to
be literally named `id`.

This is the single artifact rendered by templates, reported by discovery, and serialized to
`_generated/ir.json` (command map + SDK version) for runtime provenance and hand-written-code
introspection.

## `cli.yml` schema (override-only)

Lives at `products/<product>/cli.yml`. The classifier always runs over the live SDK; `cli.yml`
holds only deltas. Validated by a `CliConfig` pydantic model alongside `ProductConfig`.

```yaml
request:                          # map non-CRUD ops into the `request` namespace
  devices.force_reauth_devices:   {object: devices, action: force-reauth}
  configuration_management.publish_draft_configuration: {object: config, action: publish}
override:                         # fix object/verb/variant the classifier got wrong
  applications.create_application: {object: application}
hide:                             # ops intentionally excluded from the CLI
  - applications.list_application_categories
variants:                         # REQUIRED for union bodies: path-enum value -> variant model
  applications.create_application:
    path_param: type
    map: {custom: CustomApplicationInput, private: PrivateApplicationInput,
          non-web: NonWebApplicationInput, localdesktopcustom: LocalDesktopApplicationInput}
    # 'catalog' path value has no create variant — omitted intentionally
settings:                         # optional per-command tweaks (flag rename/hide/help)
  applications.list_applications: {flags: {configuration_version: {hidden: true}}}
custom:                           # thin pointer to hand-owned commands (code lives in custom/)
  commands: [prisma_browser_cli.custom.doctor]
```

## Generated CLI project (runtime behavior)

```
../prisma-browser-cli/
  prisma_browser_cli/
    _generated/              # WIPED + re-emitted every build — never hand-edited
      __init__.py
      app.py                 # build_generated_app(exclude=...) -> typer.Typer  (factory, NOT entrypoint)
      commands/<resource>.py # generated: one module per facade resource
      runtime.py             # Client.from_env(); ApiException→exit-code; JSON-flag parsing; hook dispatch
      output.py              # Rich table (default) | json | yaml
      config.py              # config.yaml + env + flag precedence
      ir.json                # serialized CliIR + built-SDK version (provenance / introspection)
    main.py                  # HAND-OWNED entrypoint: composes generated + custom  ← console_scripts points HERE
    custom/                  # HAND-OWNED: commands the generator can't infer (doctor, login, ...)
      __init__.py
    hooks.py                 # HAND-OWNED: cross-cutting hooks (before_call/after_call/confirm_delete/render_override)
    logging.py               # errors-only rotating file; --verbose → full req/resp (redacted)
  pyproject.toml             # deps: typer, rich, prisma-browser-sdk, pyyaml, platformdirs
                             # console_scripts: prisma-browser = prisma_browser_cli.main:app
  docs/COMMANDS.md           # generated command reference (typer utils docs)
  tests/                     # from products/<product>/overrides/tests/
```

See **Augmentation & extensibility** below for the generated-vs-hand-owned split and the regen contract.

- **Config:** `config.yaml` (e.g. `~/.config/prisma-browser/config.yaml`) for behavior defaults
  (`paginate`, `output`, `log_level`); `.env` for secrets. Precedence:
  **flag > env var > config.yaml > built-in default**.
- **Auth:** reuses the SDK's env var names → `Client.from_env()`.
- **Output:** Rich table default; `--output json|yaml`. Table column heuristic: `id`/`name`
  first, then scalar fields. YAML round-trips into `create --data` / `load`.
- **Pagination (`show`):** single API page by default; `--all` auto-follows cursors via
  `client.paginate(...)`; `--limit`/`--cursor` manual. Default overridable via `config.yaml`.
- **Errors:** SDK `ApiException` → friendly Rich message to stderr + nonzero exit code;
  `--verbose` writes full detail to the logfile.
- **Completion:** Typer static completion for verbs/objects/variants/flags/enum values.
- **`load`/`backup`:** per object-type. `backup <object> --file f.yaml` lists all and writes a
  YAML list; `load <object> --file f.yaml [--dry-run]` validates each entry and creates/updates.
  File format + engine designed to extend to whole-tenant (`--all`, ordered) later.

## Augmentation & extensibility

**Principle:** generated code is disposable and never hand-edited; hand-written code lives in a
stable, separate location and *layers on top*. This is the single most important property of the
design — all human augmentation lives **outside `_generated/`**, in one predictable place.

**The split:**

- **`_generated/`** — emitted wholesale on every `cli build`; deleting and re-emitting it is
  always safe. `_generated/app.py` exposes a factory `build_generated_app(exclude: set[str] = set())
  -> typer.Typer` that builds and *returns* the CRUD app — it does **not** become the entrypoint.
- **`main.py`** (hand-owned) is the `console_scripts` entrypoint. It composes the final app:

  ```python
  from prisma_browser_cli._generated.app import build_generated_app
  from prisma_browser_cli.custom import doctor

  app = build_generated_app(exclude={"set:application"})  # drop a generated command to replace it
  app.add_typer(doctor.app)                               # add a hand-written command
  app.command()(custom_set_application)                   # register the replacement
  ```

- **`custom/`** (hand-owned) — new commands the generator can't infer.
- **`hooks.py`** (hand-owned) — a small, *named* hook protocol (not an event bus) for
  cross-cutting Python. Generated `runtime.py` calls these if present, no-ops otherwise:

  ```python
  before_call(method: str, payload: Any, ctx) -> Any | None      # mutate/validate outbound payload
  after_call(method: str, result: Any, ctx) -> Any | None        # massage result before render
  confirm_delete(object: str, ident: str, ctx) -> bool           # custom confirmation
  render_override(command: str, result: Any, ctx) -> bool        # take over output for a command
  ```

**Regen contract — three ownership layers (Phase 3g: the project shell is scaffold-owned):**

- **`_generated/`** (render_cli): deleted and re-emitted on every build. Never hand-edit.
- **Project shell — scaffold-owned (overwrite every build), via `render_scaffold`:** `pyproject.toml`,
  `README.md`, `noxfile.py`, `.github/workflows/*`, `.pre-commit-config.yaml`, `.gitignore`,
  `.editorconfig`, `mkdocs.yml`, `LICENSE`, `CHANGELOG/CONTRIBUTING/SECURITY.md`, `.env.example`,
  and the `tests/` scaffold. These are version-controlled templates (in `src/phantasos/scaffold/`
  + the CLI's `cli_overrides/`), never hand-edited — exactly like the SDK. **`pyproject.toml` is
  scaffold-owned**, so custom-command dependencies are added via `cli.yml project.dependencies`
  (not by hand-editing pyproject). The SDK dependency is the SDK **distribution** name and is pinned
  to the sibling dir via a generated `[tool.uv.sources]` block until it's published to PyPI.
- **Hand-owned (emit-once, never overwritten):** `main.py` (the entrypoint), `custom/`, `hooks.py`.
- `cli.yml` stays declarative-only; it MAY carry a thin `custom:` pointer and an optional `project:`
  block (reusing the SDK's `ProjectConfig`) to supply the CLI's distribution/author/repo for the
  scaffold. The *code* lives in `custom/`, not YAML.

`phantasos cli build` runs `render_cli` (package code) then `render_scaffold` (project shell with a
CLI-shaped context built from the SDK product's context); the two write disjoint paths.

This makes "build SDK → build CLI → never hand-edit *generated*" genuinely robust while giving
humans a real place to write Python: overrides via the factory `exclude` + re-registration, new
commands via `custom/`, cross-cutting logic via `hooks.py`.

## Generation & discovery commands

Added to `phantasos.cli`:

- `phantasos cli discover <product>` — introspect + classify; print the **full classification
  table** (every resource.method → verb/object/variant or UNMAPPED) and write a `cli.yml` stub
  (CRUD pre-filled, non-CRUD/ambiguous as TODOs). This table is a **required review artifact** —
  `cli build` also prints it (the unmapped subset as warnings) so coverage gaps are never silent.
- `phantasos cli build <product>` — emit the CLI project to the sibling output dir. Requires the
  SDK to be built and importable first (errors helpfully otherwise). **Records the built SDK
  version** into `_generated/ir.json`; the generated CLI warns at runtime if the installed SDK
  version differs (mirrors the SDK's `_about.py` provenance pattern). Post-build smoke: import the
  emitted app and run `typer ... utils docs`.

## Testing strategy

- **Generator unit tests** (in phantasos `tests/`): `introspect` / `classify` / flag-mapping.
  **Seed the `classify` test matrix from the real 90-method prisma-browser inventory** (a free
  golden corpus) — e.g. `assert classify("get_application_by_id").verb == "show"`; precedence
  (skip/hide before prefix); id-param detection across `id`/`device_group_id`/`_by_type_and_id`;
  multi-method-same-verb selection; union → variant subcommands via `cli.yml variants:`;
  `cli.yml` override/hide/request merge; unmapped → warn.
- **Golden-file tests:** emitted source for a few representative commands.
- **Generated-CLI tests** (shipped via `products/<product>/overrides/tests/`): Typer `CliRunner`
  invoking commands against a **mocked SDK client** — assert the correct
  `client.<resource>.<method>(**kwargs)` call, output rendering, and error/exit codes.
- **Smoke:** emitted app imports and `typer utils docs` succeeds (wired into the framework CI
  smoke step that already builds the example SDKs).

## Open / deferred decisions (recap)

Deferred items are listed under "Deferred" in the scope section. None block v1. The only
external dependency is the SDK id-harmonization TODO, which the CLI works around by always
exposing `--id` and treating id as a single canonical path parameter per object.

## Table output & columns

### Build-time response introspection

`OperationInfo` (in `inventory.py`) carries three response fields populated by `introspect.py`:

- `return_model` — class name of the operation's return type.
- `items_field` — list-envelope field name (e.g. `"data"`), or `None` when the operation
  returns the item directly.
- `response_fields` — `list[FieldInfo]` for the *item* model (envelope unwrapped).

**Envelope detection rule:** a return model is a list envelope only when its `list[Model]`
field is named `"data"` **or** the model carries a `page_info` sibling. A plain item model
that *happens* to embed a list (e.g. `User.user_groups`) is NOT an envelope — that guard
prevents false positives on embedded collections.

### cli.yml `columns:` section

`CliConfig.columns` is a `dict[str, list[str | ColumnEntry]]` keyed by object name.
Each entry is either a bare string shorthand (`- id` → header and path both `"id"`) or a
`{header, path}` dict. `path` is a JMESPath expression evaluated at runtime against
**snake_case** row dicts produced by `model_dump(mode="json")` **without** `by_alias`.

**Build-time validation** (in `columns.py`, called from `build_cli_ir`):

- **Syntax** — every expression is compiled via `jmespath.compile`; any `JMESPathError`
  (the base class, covering empty expressions and syntax errors) fails the build immediately.
- **Root-field check** — best-effort: when the item model's fields are known and the
  AST's leftmost node is a plain field reference, an unknown root field name is rejected.
  This is intentionally lax: projected fields, function calls, and nested paths are not
  rejected just because the root key cannot be checked.
- **Unknown object keys** — any key in `cli.yml columns:` that doesn't match a known object
  noun in the IR is a hard build error (typos are caught at build time, not at runtime).

### Per-object resolution (never per command)

Column resolution is **per object**, never per command. The rationale: write-op response
models diverge (e.g. `create_device_group` returns `CreateDeviceGroup201Response{device_group_id}`,
not a `DeviceGroup` item) — validating cli.yml columns against each command's own response
model would fail the build on valid configurations.

**Object row shape** = its `show` command's item model (list envelope unwrapped; if no show
command exists, the first command with a response model is used). The resolved `columns`
list attaches to **all** commands of that object. `items_field` stays per-command (set
from each operation's own introspection result).

### Model-derived defaults

When an object has no `columns:` entry in `cli.yml`, `default_columns` generates defaults
from the item model's `response_fields`:

1. Preferred identity names first, in order: `id`, `name`, `type`, `status`, `state`
   (only those present in the model).
2. Remaining scalar/enum fields in declaration order.
3. Capped at 6 columns total.

`json`-kind fields (nested models, dicts, and complex arrays) are excluded from defaults.
Because openapi-generator emits datetime fields as `str` annotations with an `"json"` kind
after type resolution, **datetimes only appear in the table via explicit curation** in
`cli.yml`.

### Runtime `--columns` flag

`--columns` is a repeatable Typer option; each value may be a comma-separated list of
JMESPath expressions. Commas inside `[]`, `()`, `{}`, and quotes/backticks are protected
(top-level comma split only). Naming syntax: `HEADER=expr` assigns a display header; a
lone `=` separator (`==` comparison operators pass through unmodified).

**`--columns` implies table and wins over an explicit `--output json|yaml`.** This is a
deliberate UX decision: if the user asks for columns, they want a table — `--output` is
demoted. Default output format remains `json`; "show defaults to table for list results" is
a roadmap follow-up (phase-3 roadmap 3×), not part of this feature.

Invalid expressions at runtime print a markup-safe error to stderr (Rich `markup=False`)
and exit 2.

### Table rendering

At render time (`output.py`):

1. **Unwrap envelope** — if `items_field` is set, `data[items_field]` is the row list;
   otherwise the result is wrapped in a single-element list.
2. **Column selection priority:** `--columns` > IR `columns` > data-driven heuristic.
3. **Cell formatting:**
   - `None` → empty string.
   - `bool` → `"true"` / `"false"`.
   - `list` → joined preview: `"a, b, c, +2 more"` (dicts labeled by `name`/`id` key, else
     `"N items"`).
   - `dict` → compact JSON (`separators=(",", ":")`).
   - Scalar values → `str(value)`.
4. **Empty rows** → `"[dim]no results[/]"`.
5. **Data-driven heuristic (last resort)** — when neither `--columns` nor IR columns are
   available, top-level scalar-ish keys are collected from the live data with preferred
   names first, capped at 6. These use a plain `dict.get` lookup (`_Key` wrapper), never
   `jmespath.compile` — raw API keys are not guaranteed to be valid JMESPath identifiers
   and the heuristic must never exit.

### discover stub pre-fill

`discover.py`'s `render_stub` emits a `columns:` block (flow-style, deduplicated per
object) populated with the model-derived defaults. The stub author can then curate or
replace entries. Only objects whose IR already carries resolved columns appear in the stub.

### oneOf union items (e.g. prisma `ApplicationItem`)

For union wrapper models (detected by an `actual_instance` field), `model_dump` walks
through the wrapper, so curated JMESPath expressions must go **through** the wrapper field:
`actual_instance.id`, `actual_instance.name`, etc. A bare `id` path evaluates against the
wrapper's own fields and renders empty.

### Known limitations

The `discover` stub does **not** round-trip through `load_cli_config` when there are no
request mappings: a bare `request:` key in the emitted YAML is parsed as `None` rather than
`{}`, which means reloading the stub and calling `load_cli_config` raises a pydantic
validation error. This is a pre-existing parser quirk in the ruamel.yaml/pydantic boundary,
not introduced by the columns feature. Tracked as tech debt; workaround: the stub is
intended as a starting point for hand-curation, not as a round-trippable machine format.

## Per-op query-param defaults (`defaults:`)

### Section shape

`cli.yml` carries an optional `defaults:` block keyed by `<resource>.<method>` (the same
namespace as `override:`, `hide:`, etc.) → query-param name → scalar value:

```yaml
defaults:
  applications.list_applications:       {sort: application.id, order: asc}
  applications.list_applications_by_type: {sort: application.id, order: asc}
```

Only **query** parameters are accepted; path parameters and body fields are rejected at build
time (unknown op name or non-query param → hard build error, not a warning).

### Semantics

Defaults are **always applied** to the SDK call unless the user explicitly overrides them on
the command line. They surface in `--help` as the displayed default value (Typer renders the
`default=` kwarg in the option definition) so they are discoverable without reading `cli.yml`.
They are **user-overridable**: any value the user passes for that flag wins; the injected
default is only used when the flag is absent from the invocation.

### IR representation (`Flag.cli_default`)

The `Flag` model carries two distinct default fields:

- `Flag.default` — the **model default** as declared in the SDK's pydantic field (e.g.
  `Field(default=None)`). This is **never rendered** into the generated Typer option. Rendering
  model defaults would silently inject SDK-level sentinels into every PATCH call, corrupting
  partial-update semantics. The field is retained in the IR for introspection only.
- `Flag.cli_default` — the **CLI default** sourced exclusively from `cli.yml defaults:`. This
  is the value rendered as `default=` in the generated option definition. `None` means no
  default is shown.

This invariant (`cli_default` comes only from `cli.yml`, never from the model) is the PATCH
safety guarantee: the generated CLI never unilaterally sends fields the operator didn't
author.

### Runtime binding guard

A `show <object>` command may aggregate multiple SDK method bindings (e.g. `list_applications`
and `list_applications_by_type` for the `application` object). A `defaults:` entry is authored
for a specific method; its injected defaults may reference query params that exist in one
binding's signature but not another's.

At runtime, after the active binding is selected from the supplied flags, injected defaults
that the **selected binding's signature does not accept** are silently dropped before the SDK
call is made. Selection uses credential-free class inspection (`inspect.signature` on the
bound method's class); the guard is **fail-open** — if inspection fails for any reason the
call proceeds without the injected defaults rather than raising.

This ensures that e.g. `show application --type catalog --id <ID>` (which selects
`get_application_by_type_and_id`) never receives a `sort` kwarg, which would cause a
validation error, even though `sort` is a listed default for the `list_applications` binding.

### Motivating case: applications cursor quirk

The Prisma Access Browser API honors application-list pagination cursors **only when an
explicit `sort` parameter is present** in every page request. Without `sort`, the server
returns at most 100 results and subsequent cursor requests return empty pages — `--all` silently
truncated at 100.

The fix ships as `cli.yml` defaults on both application list operations:

```yaml
defaults:
  applications.list_applications:         {sort: application.id, order: asc}
  applications.list_applications_by_type: {sort: application.id, order: asc}
```

This approach was chosen over an SDK-level or runtime-pagination fix because:

1. The quirk is product-specific and belongs in the product's `cli.yml`, not in the generic
   pagination engine.
2. Surfacing `[default: application.id]` in `--help` makes the behaviour auditable and
   overridable by the operator.
3. The runtime binding guard (above) prevents these defaults from leaking into the single-item
   `get_application_by_type_and_id` path.

Live verification: `show application --all --name google` returns **108 items, 108 unique**
(was 100 before the fix).
