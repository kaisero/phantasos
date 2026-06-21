# cli-generator

Validated against 50c1e34 on 2026-06-14 · Purpose: how `phantasos cli build` turns a BUILT SDK into a vendored, scaffolded Typer + Rich CLI project.

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
this package. They wire the three pipeline stages together:

1. **Introspect** — `introspect.introspect(package, sdk_path)` in `introspect.py`
   imports the built SDK, reads `extras.facade._RESOURCES`, and walks each
   resource class's public methods via reflection (signatures, type hints,
   docstrings, pydantic model fields). It produces an `OperationInventory`
   (`inventory.py`: `OperationInfo` / `ParamInfo` / `FieldInfo`), classifying each
   param as path / query / body and capturing the response model + list-envelope
   `items_field` for table columns. The `body_fields` map records oneOf-variant
   model fields. For a oneOf **list** item, `_item_fields` reports the union
   (superset) of the variant models' fields — not the wrapper scaffolding — so
   default and curated columns resolve against real variant fields (bare names,
   no `actual_instance.` prefix).
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
3. **Render** — `render_cli.render_cli(ir, package, out_dir, *, env_prefix,
   distribution, auth)` in `render_cli.py` wipes/re-emits `_generated/` from Jinja
   templates: the runtime modules, one command module per SDK resource, the
   `app.py` factory, a typed copy of the IR models (`spec.py`, copied from
   `ir.py`) and `ir.json`. The `auth` parameter is the product's resolved auth
   component (`loaded.auth`, passed by `cli_build`); when present, its
   `credential_fields()` enrich a `model_copy` of the IR (`ir.credential_fields`)
   BEFORE any template render or the `ir.json` write, so templates, `spec.py`, and
   the serialized IR all see the same enriched copy. That field gates the
   auth-only emissions (`environment_commands.py`, the `environment` app, the
   credential pre-flight). The `errors` parameter (`loaded.errors`) is enriched the
   same way: its `error_fields()` populates `ir.error_envelope`, so the emitted
   `diagnostics._error_headline` is config-driven (peel `wrappers` → `error_field` →
   `errors_field` → product-AGNOSTIC `fallback_keys`) and carries NO product-specific
   error keys; with no error component the default generic envelope applies. It
   `ruff`-formats only the files it wrote, then emits
   the hand-owned files (`main.py`, `hooks.py`, `custom/__init__.py`) ONCE (never
   overwritten on rebuild). `cli_build` then lays down the project scaffold via
   the sibling `scaffold` module, using
   `scaffold_context.build_cli_scaffold_context()` (the SDK product context
   overridden for the CLI) and `cli_overrides/` as the override tree.

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
- **Named environments** (auth CLIs only) — credentials stored in
  `~/.{distribution}/environments.yml` (`environments:` + `default_environment:`,
  `${VAR}` refs expanded at read time). Top-level `environment` command group
  (`create`/`activate`/`show`/`delete`; `show` never prints values, `delete`
  --force-gates the active env, first create auto-activates; `create`'s
  per-credential options are built from `ir.credential_fields`). Active env
  resolves `-e/--environment` flag > `{PREFIX}_ENVIRONMENT` env var >
  `default_environment`; per-field credential env vars still override the env.
  Helpers in the emitted `config.py` (`resolve_environment`, `default_environment`)
  + `runtime.py` (`select_environment`); commands in `environment_commands.py.jinja`.
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

## Build / run pointers

- Inspect classification: `phantasos cli discover <name>` (`--write-stub` writes
  `products/<name>/cli.yml.stub`). Needs the SDK built and importable.
- Emit the CLI project: `phantasos cli build <name>` (writes a sibling
  `<sdk-dist>-cli/` project next to the SDK).
- Tests (`ls tests | grep -i cli`): `test_cli.py`, `test_cli_classify.py`,
  `test_cli_columns.py`, `test_cli_command.py`, `test_cli_config.py`,
  `test_cli_discover.py`, `test_cli_emitted.py`, `test_cli_emitted_real.py`,
  `test_cli_introspect.py`, `test_cli_ir.py`, `test_cli_render.py`,
  `test_cli_scaffold.py`. Behavioral tests run through the emitted package
  (`tests/test_cli_emitted.py` `emitted` fixture); config is cached at command-
  module import (set HOME/env before import; `load_config.cache_clear()` after
  mutating env).

## Module map

<!-- GENERATED:module-map -->
- `classify.py` — Deterministic classification of SDK methods into the CLI command tree.
- `cliconfig.py` — The per-product cli.yml model — declarative deltas only; the classifier always runs.
- `columns.py` — Table-column resolution: model-derived defaults + cli.yml validation.
- `discover.py` — Render the classification table and a cli.yml stub from a CliIR.
- `introspect.py` — Import a built SDK and produce a typed OperationInventory.
- `inventory.py` — Typed output of SDK introspection (the input to classification).
- `ir.py` — The CLI intermediate representation: the fully-resolved command tree.
- `render_cli.py` — Emit a Typer CLI project from a CliIR (static codegen via Jinja).
- `scaffold_context.py` — Build the scaffold context for an emitted CLI project (reuses the SDK scaffold).
<!-- /GENERATED:module-map -->

## Public API

<!-- GENERATED:api -->
- `classify.py`
  - class `Classification`
  - `classify_name(method)` — Prefix-heuristic classification. Returns None for unmapped/skip ops.
  - `detect_id_param(params)` — The id is the single required path param that is not a discriminator enum.
  - `select_method_for_verb(methods)` — Return the preferred method when multiple share the same verb.
  - `fields_to_flags(fields)`
  - class `ResolvedVariant`
  - `resolve_variants(op, vmap)` — Map a method's path-enum values to variant models via cli.yml (the SDK oneOf
  - `build_cli_ir(inv, cfg)`
- `cliconfig.py`
  - class `RequestMapping`
  - class `Override`
  - class `VariantMap`
  - class `ColumnEntry`
  - class `CustomPointer`
  - class `CliConfig`
  - `load_cli_config(path)` — Load cli.yml; return an empty CliConfig if the file is absent.
- `columns.py`
  - `default_columns(fields)` — Preferred names first, then remaining scalar/enum fields in declaration
  - `resolve_columns(entries, fields, obj)` — Normalize cli.yml column entries; raise ValueError (-> build failure) on
- `discover.py`
  - `render_table(ir, unmapped)`
  - `render_stub(ir, unmapped)` — A cli.yml stub: TODO entries for unmapped ops. CRUD is auto-classified, so the
- `introspect.py`
  - `introspect(package, sdk_path)`
- `inventory.py`
  - class `ParamInfo`
  - class `FieldInfo`
  - class `OperationInfo`
  - class `OperationInventory`
- `ir.py`
  - class `CredentialField` — Describes one credential field exposed by an auth component.
  - class `ErrorEnvelope` — Config-driven description of a product's error body, threaded onto the IR so
  - class `Flag`
  - class `MethodBinding`
  - class `ColumnSpec` — One table column: a header + a JMESPath evaluated against each row dict
  - class `Command`
  - class `CliIR`
- `render_cli.py`
  - `cli_overrides_dir()`
  - `render_cli(ir, package, out_dir, env_prefix, distribution, auth, errors)`
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

## See also

- Specs: `docs/specs/2026-06-09-cli-generator-design.md` (design), plus the WP
  specs listed under *Emitted features*.
- Recipe: `CLAUDE.md` → "Adding a CLI configuration option (generated CLIs)".
- Adjacent docs: `sdk-generator.md` (the SDK this consumes),
  `product-config.md` (`productconfig.py` loader), `components.md` (component
  param models).
