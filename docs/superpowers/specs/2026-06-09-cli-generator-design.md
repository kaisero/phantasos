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
CRUD CLI (`set`/`del`/`show`). Unlike that hand-written CLI (~480 lines/resource), ours is
generated from the SDK, so commands map 1:1 to real SDK calls with no hand-maintained
name-mapping layer.

Research + recon backing this design: `docs/research/2026-06-09-cli-generator.md`. Key verified
conclusions: prefer **static codegen via Jinja** over runtime/dynamic construction (also
required for `typer utils docs` + shell completion to work); mirror **pydantic-settings**
field→flag semantics; the cdot65 verb-first pattern is the model.

### In scope (v1)

The IR-centric generator and a working `prisma-browser-cli` with: verbs `set`/`del`/`show`/
`request`/`load`/`backup`; full flag generation (scalars → typed flags, complex/union fields →
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
  body-model params it recurses `model.model_fields`, resolving discriminated-union variants.
  Output: a typed `OperationInventory`.
- **`classify.py`** — applies the classifier rules (below), merges `cli.yml` deltas, and
  produces the typed **`CliIR`** — the fully-resolved command tree. Pure and unit-testable.
- **`render.py`** — Jinja templates walk `CliIR` and emit standalone CLI source modules.
- **`discover.py`** — consumes the *same* `CliIR` to print a human report and write a `cli.yml`
  stub. Generation and discovery therefore cannot drift.

This mirrors phantasos's existing `productconfig → render` typed-model pattern.

## Command grammar & taxonomy

Verb-first: **`<verb> <object> [<variant>] [flags]`**

- **Verbs:** `set` (create/patch/update), `del`, `show`, `request` (non-CRUD actions),
  `load` (bulk import), `backup` (export).
- **Object** = facade resource **+ method noun**, so one facade resource splits into its real
  object types: `access_and_data_policy` → `access-and-data-rule`, `access-and-data-section`, …
- **Variant** = a body-level discriminated-union member: `set application custom|private|…`.
  When a path discriminator (e.g. the `type` param) matches the body discriminator, the variant
  subcommand sets both.
- **`set` resolution:** no `--id` → create (POST); `--id` + fields → patch (PATCH, default);
  `--id --replace` → update (PUT). If an object has only one write verb, `--id` uses it.
- **`--dry-run`** on every mutating verb (`set`/`del`/`load`/`request`): print the resolved SDK
  call + payload, do not execute.

### Classifier rules

| Method prefix | CLI verb |
|---|---|
| `create_` | `set` (create) |
| `patch_` | `set` (patch) |
| `update_` | `set` (update; `--replace`) |
| `delete_`, `bulk_delete_` | `del` |
| `get_`, `list_` | `show` |
| `bulk_create_` | `set --bulk` |
| anything else | unmapped → needs `cli.yml` |

**Object noun:** strip the verb prefix and any trailing `_by_id` / `_by_type_and_id` /
`_by_type`, then singularize (`list_applications` → `application`). Methods sharing a noun group
under one object.

**Unmapped policy: warn + skip.** Ops that don't classify (e.g. `suspend_*`, `archive_*`,
`force_reauth_*`, `revoke_*`, `publish_*`, `*_positions`, sub-resource reads like
`list_application_categories`) are listed in a build warning with guidance, and omitted from the
CLI until mapped in `cli.yml`. No `cli.yml` → CRUD-only + warnings.

### Flag generation (mirrors pydantic-settings)

- **Scalar / enum / simple-list** field → an individual typed flag (`--name`, `--enabled`,
  `--urls`). Enum fields carry `choices` (drive static completion); enum values may contain
  spaces/hyphens.
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

class Command(BaseModel):
    verb: Literal["set", "del", "show", "request", "load", "backup"]
    object: str                     # kebab-case object noun
    variant: str | None             # union variant, if any
    sdk_resource: str               # facade attribute, e.g. "applications"
    sdk_method: str                 # e.g. "create_application"
    path_params: list[Flag]
    body_flags: list[Flag]
    query_flags: list[Flag]
    summary: str
    description: str
    paginated: bool

class CliIR(BaseModel):
    commands: list[Command]
```

This is the single artifact rendered by templates, reported by discovery, and (potentially
later) serialized to a JSON command map.

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
settings:                         # optional per-command tweaks (flag rename/hide/help)
  applications.list_applications: {flags: {configuration_version: {hidden: true}}}
```

## Generated CLI project (runtime behavior)

```
../prisma-browser-cli/
  prisma_browser_cli/
    main.py                  # Typer app; registers set/del/show/request/load/backup sub-apps
    commands/<resource>.py   # generated: one module per facade resource
    config.py                # config.yaml + env + flag precedence
    output.py                # Rich table (default) | json | yaml
    runtime.py               # Client.from_env(); ApiException→exit-code; JSON-flag parsing
    logging.py               # errors-only rotating file; --verbose → full req/resp (redacted)
  pyproject.toml             # deps: typer, rich, prisma-browser-sdk, pyyaml, platformdirs
                             # console_scripts: prisma-browser = prisma_browser_cli.main:app
  docs/COMMANDS.md           # generated command reference (typer utils docs)
  tests/                     # from products/<product>/overrides/tests/
```

- **Config:** `config.yaml` (e.g. `~/.config/prisma-browser/config.yaml`) for behavior defaults
  (`paginate`, `output`, `log_level`); `.env` for secrets. Precedence:
  **flag > env var > config.yaml > built-in default**.
- **Auth:** reuses the SDK's env var names → `Client.from_env()`.
- **Output:** Rich table default; `--output json|yaml`. Table column heuristic: `id`/`name`
  first, then scalar fields. YAML round-trips into `set --data` / `load`.
- **Pagination (`show`):** single API page by default; `--all` auto-follows cursors via
  `client.paginate(...)`; `--limit`/`--cursor` manual. Default overridable via `config.yaml`.
- **Errors:** SDK `ApiException` → friendly Rich message to stderr + nonzero exit code;
  `--verbose` writes full detail to the logfile.
- **Completion:** Typer static completion for verbs/objects/variants/flags/enum values.
- **`load`/`backup`:** per object-type. `backup <object> --file f.yaml` lists all and writes a
  YAML list; `load <object> --file f.yaml [--dry-run]` validates each entry and creates/updates.
  File format + engine designed to extend to whole-tenant (`--all`, ordered) later.

## Generation & discovery commands

Added to `phantasos.cli`:

- `phantasos cli discover <product>` — introspect + classify; print the report (resource.method
  → verb/object/variant or UNMAPPED) and write a `cli.yml` stub (CRUD pre-filled, non-CRUD as
  TODOs).
- `phantasos cli build <product>` — emit the CLI project to the sibling output dir. Requires the
  SDK to be built and importable first (errors helpfully otherwise). Post-build smoke: import the
  emitted app and run `typer ... utils docs`.

## Testing strategy

- **Generator unit tests** (in phantasos `tests/`): `introspect` / `classify` / flag-mapping
  against small fixture SDKs and the real prisma-browser SDK — e.g.
  `assert classify("get_application_by_id").verb == "show"`; union → variant subcommands;
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
