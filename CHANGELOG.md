# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Federated (multispec) CLI generation** — `cli build` can now generate a CLI that spans a federated SDK's sub-packages, producing a `verb → sub-package → object` command hierarchy from a single `cli.yml` with a `subpackages:` enrollment map. The map is an allowlist: list the subs to include (e.g. objects + incidents for a first release), or omit it to enroll all. Cross-sub object-name collisions and unmapped federated non-CRUD operations are hard build errors. Single-spec CLIs are behaviorally unchanged.
- **prisma-access CLI (P0: objects + incidents)** — the first federated CLI built with this system: `prisma-access show objects address list`, `prisma-access request incident search`, and the full CRUD surface for both enrolled sub-packages. Region and tenant are **connection fields** sourced from `sdk.yml` `default_headers`: stored per named environment alongside credentials, exposed as global `--region`/`--tenant` flags, and enforced by a command-aware pre-flight that only demands a field for the sub-packages that declare it (objects CRUD runs region-unset — verified live). Sub-package SDK client handles are built lazily — the region header is only required when the sub-package that needs it is first invoked.
- **Discoverability in generated federated CLIs** — `which <object>` prints the sub-package and supported verbs for a named object, with `did-you-mean` suggestions on a miss; `phantasos cli discover` now renders per-sub-package classification tables for federated SDKs; per-object and per-sub-package `--help` surfaces the full command tree.
- Generated SDKs for SCM-family specs (prisma-access) now reshape each "configurable
  object" body so it can carry its real fields. openapi-generator keeps only the
  `oneOf`/`anyOf` "exactly one of folder/snippet/device" container and discards the
  sibling payload, leaving body models that can express nothing but placement; a new
  guarded preprocess transform (`flatten_scm_bodies`, fires on 119 schemas across the
  12 specs) lifts every reachable composition leaf back onto the model as optional
  fields, while `relax_readonly_required` drops server-assigned `readOnly` fields
  (`id`, …) from `required` so `create()` no longer demands them. Real nested
  value-unions (lacking the placement marker) are left untouched. A live CRUD
  round-trip on `objects.tag` and `objects.address` proves the reshaped bodies are
  accepted on-wire (`{name, ip_netmask, folder}`, not just `{folder}`).
- **Federated SDKs now ship a runtime live smoke** (`tests/test_federated_live.py`,
  emitted only for federated distributions). It loops the composer's `_SUBPACKAGES`
  and makes one real authenticated collection read per sub — auto-picking the first
  object with a zero-arg `list`, or a per-sub `live_smoke:` override (`$ENV` args
  resolved at runtime; a non-string arg such as a `{}` request body passes through) —
  to prove each sub's auth/base-path/region **wiring** (a 404/401/424 fails;
  `test_scm_crud_live.py` remains the functional proof). Because the smoke checks
  wiring, not model fidelity, a response that *arrives* but can't be parsed by an
  over-strict or wrong-shaped generated model is a **pass** (the request reached the
  tenant); only a pre-HTTP arg-validation error (a bad probe) still fails. Overrides
  are validated against the built SDK at build time. Skips without live credentials.
  Proven green against the real prisma-access tenant — all 12 sub-packages, including
  ZTNA (probed via `connector_group`; its earlier 424 was a spec base-path bug, since
  fixed). Supersedes the prisma-access first-light smoke.
- SDK generation translates OpenAPI `\p{...}` Unicode-property regex patterns (valid in
  PCRE/ECMAScript, **invalid** in Python's `re`) to permissive Python-valid equivalents,
  so generated pydantic models no longer raise `PatternError` deserializing responses
  (e.g. ZTNA's `^[\p{L}\p{N}\p{P}...]*$` fields).
- Generated SDK reference docs now render openapi-generator anyOf/oneOf **wrapper**
  model pages as the real payload (synthesized field tables, grouped by branch) with
  the SCM container collapsed to a one-line `Placement:`, instead of the
  `anyof_schema_*`/`actual_instance` scaffolding; the wrapper-body **example** in the
  quickstart now synthesizes a constructable, fully-nested form. Applies to every
  wrapper page (both products).
- **Every model reference page is now a field table.** A plain model page renders a
  `Field | Type | Required | Default | Description` table — replacing the mkdocstrings
  autodoc, which leaked pydantic `Config:`/`Validators:` and the OpenAPI boilerplate. A
  genuine one-line model description (e.g. the SCM "supply exactly one of
  folder/snippet/device" hint) is kept above the table; boilerplate is dropped. Each
  page keeps a heading-only autodoc block so its anchor — and every inbound
  cross-reference — still resolves under `mkdocs build --strict`. Wrapper pages use the
  same table for their inline variant fields.
- In those tables, a field whose **type is itself a documented model** (including
  `list[Model]`, which keeps its container) renders as a clickable mkdocstrings
  cross-reference to that model's page, so a reader can drill into the nested shape in
  one click instead of reading dead type text; scalars and `list[str]`/`dict[...]` stay
  plain.

- Generated CLIs now carry a deduped nested-schema model registry in the CLI IR
  (`CliIR.models` + per-flag `Flag.model_ref`), recovering the full structure of
  complex (`json`-kind) body fields that previously collapsed to an empty `TEXT`
  flag with a `'{}'` example. One registry-driven skeleton synthesizer (shipped
  verbatim to the runtime) powers four surfaces: progressive-disclosure docs
  (collapsible per-flag schema tables, `oneOf` tabs, and a copy-&-fill full-body
  skeleton on each command's reference page); a `[json: <Model>] e.g. {…}` `--help`
  annotation carrying a real, minimal, valid skeleton; that same skeleton in the
  docs one-line invocation (replacing `'{}'`); and a debug-adaptive JSON skeleton
  in input-error messages (the full body under debug logging, an always-valid
  minimal body otherwise). All-optional models still emit one representative field,
  so the suggested body is never an API-rejected `{}`.
- Generated CLIs can now emit a documentation site — opt-in via a `docs:` block in
  `cli.yml` (`showcase_object`, optional `showcase_variant` / `site_name` /
  `examples`). `cli build` renders a standalone MkDocs-Material site (Home with a
  verb-model explainer, Quickstart, a per-object command reference with full flag
  tables and synthesized examples, and Output / Pagination / Authentication / Errors
  guides) directly from the CLI IR — no mkdocstrings and no CLI import needed at docs
  build. Built strict in CI via a new `cli-docs` nox session; enabled for
  prisma-browser and posture.
- Generated SDK reference docs now render typed wrapper signatures with clickable
  request-body model links, and a synthesized copy-pasteable example under every
  operation (all-optional update bodies render `body=Model()  # all fields optional`).
  The showcase resource honors `docs.showcase_variant` / `docs.examples` on its
  reference page.
- Agent-facing context docs (`.agents/context/`) — a modular, on-demand technical
  doc set for in-repo coding agents: an `index.md` system map, per-subsystem
  deep-dives (sdk-generator, cli-generator, components, product-config, scaffold,
  phantasos-cli, harness-and-testing, release-workflow), and cross-cutting
  `decisions.md` / `goals-non-goals.md`. An AST generator (`nox -s context`,
  `tools/context_docs.py`) fills the mechanical sections (module maps, public API)
  with a `--check` mode enforced by a test; discoverable via a root `AGENTS.md`
  and a `CLAUDE.md` pointer. Includes an A/B evaluation harness (`tools/ab_eval/`).
- Generated CLIs now write a structured, rotating JSON-Lines log to `~/.{distribution}/logs/{distribution}.jsonl` (private `0o600`, gzip-rotated). Python `warnings` (notably the SDK's lenient-enum pass-through) and CLI diagnostics are captured into this file instead of the terminal; a single terse stderr line at exit summarizes any unknown API enum values. A new `logging` config section (`level` — trace/debug/info/warning/error/critical — and `file`) joins the layered-config flow, with `{PREFIX}_LOGGING_LEVEL` / `{PREFIX}_LOGGING_FILE` env overrides.
- `config set <key> <value>` and `config unset <key>` for generated CLIs: write/remove options in `config.yml` (aliases `loglevel`/`logfile`; values coerced by type; unknown keys and invalid values exit `2`). NOTE: writing `config.yml` strips the comments that `config init` wrote — run `config init --force` to restore the commented template.
- Generated CLIs with an auth component now support named environments: stored in `~/.{distribution}/environments.yml` (top-level `environments:` and `default_environment:` keys, with `${VAR}` references resolved at read time), an `--environment/-e` flag, and a `{PREFIX}_ENVIRONMENT` selector. Per-field credential env vars override the active environment.
- Top-level `environment` command group (auth CLIs only; shown in the `--help` "CLI" panel beside `config`): `create` (per-credential-field options built dynamically from the auth component; secrets prompted with input hidden and stored verbatim, including `${VAR}` references), `activate`, `show` (names only — never values/secrets; marks the active environment), and `delete` (`--force` required to remove the active environment). The first environment created is auto-activated.
- Typed `client.<object>.<verb>(...)` resource wrappers in generated SDKs; the
  generated CLI now dispatches through them. New `sdk.yml operations:` naming override
  block for declarative per-op `resource`/`method`/`verb` overrides (keyed by
  `api_attr.raw_method`; validated at build) — including a per-op `hide: true` that
  drops an op from the wrapper entirely (SDK analog of `cli.yml hide:`).
- Generated SDKs can now ship a complete Material for MkDocs site (Getting Started,
  Architecture, authentication/pagination/CRUD how-to guides, and an mkdocstrings API
  reference). Opt in per product via a `docs:` block naming a `showcase_resource`; the
  guides are tailored to that resource via a scoped, build-time introspection. The site
  builds under `mkdocs build --strict`. Products without a `docs:` block emit no docs
  (and no longer ship the previously non-building mkdocs shell).
- Generated SDK docs now render each pydantic model's full field surface (via
  `griffe-pydantic`), document oneOf wrapper types as links to their variant
  models, and emit real-shaped CRUD examples synthesized from the schema.
- `sdk.yml` `docs:` gains `showcase_variant` (choose the oneOf variant used in
  the example) and `examples.<slot>` (verbatim per-operation example override).
- New **posture** product (Palo Alto Networks Posture Management & Assessment —
  BPA config upload + Custom Posture Checks): generates a working SDK and CLI
  (`posture-sdk` / `posture-cli`). Full CLI surface — CRUD on `posture-check`,
  `request posture-check clone|batch-upsert|batch-delete`, `request bpa upload`,
  and `show bpa-result`. Vendor spec is read-only; a `hooks.py` preprocess promotes
  the non-standard `ExternalTags` block to a standard root `tags:` array, renames
  the tag to `Posture Checks` (→ `client.posture_checks`), injects the missing
  bearer `securitySchemes`/`security` so the SDK attaches the SCM OAuth token, and
  adds illustrative create/update examples.
- New **offset/limit pagination** component (`pagination: {type: offset}`): a
  `paginate()` helper that walks `limit`/`offset` pages (owning a `default_page_size`
  since the runtime forwards neither flag unless set), stopping on a short page or
  `offset >= total`. Complements the existing `cursor` strategy.
- New **list-style error** component (`errors: {type: list_error}`): formats the
  `{"_errors": [{"code", "message"}, ...]}` envelope as `code: message` (joined).
- Generated CLI error rendering is now **config-driven**: each error component
  contributes an `ErrorEnvelope` descriptor (`error_fields()`) that `render_cli`
  threads onto the IR (like `auth.credential_fields`), so the emitted
  `diagnostics._error_headline` peels the product's configured `wrappers` →
  `error_field` → `errors_field`, then a product-AGNOSTIC `fallback_keys` set. The
  generic CLI template carries NO product-specific error keys (a product's envelope
  shape never leaks into another product's CLI); the SCM gateway's `{"msg": …}` 403
  shape rides the generic fallback tier, so a denied request reads
  `error: 403 Forbidden — Access denied`. The `nested` component's `errorResponse`
  wrapper is now documented config (`NestedError.wrappers`) and the SDK helper unwraps
  it too (previously only the CLI did — a latent divergence).
- CLI classifier now recognizes **PUT full-replace updates** (`update_*` →
  `update <object>`, sub_verb `put`): unlike PATCH, a PUT keeps the model's required
  body fields required (omitting one would wipe it server-side). A command merging
  both a PATCH and a PUT binding relaxes to optional (PATCH offers partial updates).

### Changed

- `list(all_pages=True)` replaces the CLI-side pagination loop: the wrapper's
  `.list(all_pages=True)` paginates internally and returns a full envelope
  (`page.model_copy(update={"data": items})`); the runtime passes `--all` as
  `all_pages=True`. Raw `*Api` classes are no longer reachable from `client.<object>`.
- User-facing docs: a new **Architecture** page (intent, scope, and three-layer + build-pipeline Mermaid diagrams); the Home page rewritten with a minimal first-build; the authoring guide renamed to `authoring.md` with a quickstart on top.
- Contributor tooling: product enrollment for the `smoke`/`live`/`sdk-docs` nox sessions now lives in a root `nox.toml` (per-stage `products` lists + per-product `sdk-docs` content assertions) instead of being hardcoded in `noxfile.py`. The new **posture** product is now gated by both `smoke` and `sdk-docs`.

### Fixed

- The SDK patch step now repairs an openapi-generator defect where a `oneOf` wrapper
  names a branch model it also renders as a primitive validator (e.g. a numeric
  `Number` branch) without importing it — a dangling forward reference that only
  surfaces once the SCM body reshape restores deep payloads and breaks
  `model_rebuild()` during introspection/docs.
- Generated CLIs now render clean payloads for oneOf endpoints (e.g. `show access-and-data-policy`): the openapi-generator wrapper scaffolding (`actual_instance`, `one_of_schemas`, `oneof_schema_*_validator`, `discriminator_value_class_map`) no longer leaks into `--output json/yaml`, and empty `additional_properties: {}` bags are omitted (non-empty bags — fields the spec hasn't caught up to — are preserved). Two generic SDK serializer patches drive this, so every `model_dump()` consumer benefits; the outbound request path (which uses `to_dict()`) is unchanged. Curated/default table columns for oneOf list commands now resolve against the real variant fields (e.g. `application`, `access-and-data-policy`) instead of showing the wrapper.
- Generated CLIs (with an auth component) now report a clean, actionable error instead of a raw traceback when no credentials are configured on the first command: a descriptor-driven pre-flight names the missing required credential variables (and the active environment, if any) and points to both `environment create` and the credential env vars (exit code `2`). A genuine auth failure when credentials *are* present (e.g. a token-endpoint error) is likewise reported cleanly with exit code `1`; `--verbose` still surfaces the traceback. The SCM `base_url` credential is now correctly treated as optional (the SDK host has a default).
- Generated CLIs now report a clear error when a `show <object>` is backed only by a get-by-id operation and the API exposes no list endpoint (e.g. `show access-and-data-rule`, `show access-and-data-section`): instead of the generic `no operation for '…' matches the given arguments`, the CLI prints `'show <object>' has no list operation` with a hint to fetch a single object by `--id` (exit code `2`). Detected at build time via a new `Command.get_by_id_only` IR flag.
- CLI docs: nested-model body flags (e.g. `--microsoft`) now show the model's
  schema-level description in the Body table, and the Type cell links to that
  flag's schema disclosure block.

### Removed

- Obsolete `docs/ARCHITECTURE.md` (a stale "proposal" describing a superseded
  layout) and its references — superseded by the `.agents/context/` set; the
  published-site nav entry is dropped (a fresh architecture page belongs to the
  user-facing docs rework).
- The mkdocstrings-generated API reference (replaced by a hand-written CLI reference page) and `docs/ONBOARDING.md` (folded into the authoring quickstart).
- `sdk.yml` `docs.operations` (the per-verb showcase method override) — dead config after CRUD verbs became wrapper-canonical (it was never consumed).

## [0.1.0a1] - 2026-06-13

### Added

- Generated CLI subsystem (Typer + Rich) from built SDKs — verb-first set/del/show, IR-driven
- cli.yml-driven config: per-op query defaults, curated table columns (`--columns`)
- Layered user config + auto-pager + JSONL command history for generated CLIs
- Diagnostics/error UX overhaul (stderr facade, `--quiet`, help panels)
- SDK generator: oneOf discriminator lookup
- SDK generator: retry-with-jitter (Tier-1 component) + typed `RateLimitException` (Tier-2 `exceptions.mustache`)

### Changed

- **Breaking:** host CLI moved to Typer — `phantasos build` is now `phantasos sdk build`; adds `phantasos cli discover` / `phantasos cli build`
- Generator code split into `generator/{sdk,cli}` packages

### Fixed

- `typer` is now a runtime dependency (was dev-only — a pip-installed CLI crashed on import)
- The wheel now ships the generated-CLI templates + `cli_overrides` (were absent — `phantasos cli build` failed from a wheel)

## [0.0.1] - 2026-01-01

### Added

- Initial release of phantasos.

[Unreleased]: https://github.com/kaisero/phantasos/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/kaisero/phantasos/compare/v0.0.1...v0.1.0a1
[0.0.1]: https://github.com/kaisero/phantasos/releases/tag/v0.0.1
