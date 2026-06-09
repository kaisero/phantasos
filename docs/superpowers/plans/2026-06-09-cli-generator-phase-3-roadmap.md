# CLI Generator — Phase 3 Roadmap & Handoff

**Date:** 2026-06-09
**Status:** Planning / handoff (not a TDD plan — write per-sub-phase plans via `writing-plans` when picking each up)
**Branch:** `cli-generator` (HEAD at Phase 2b completion)

This document lets a future session resume the phantasos CLI-generator feature. Read it
alongside the **spec** (`docs/superpowers/specs/2026-06-09-cli-generator-design.md`) and the
project **memory** (`prisma-browser-cli-generator-design`).

## Where things stand (done)

- **Phase 1** — generator core + `phantasos cli discover`. (plan: `…phase-1-core-and-discover.md`)
- **Phase 2a** — aggregated command IR (one `Command` per `(verb,object,variant)` with
  `bindings`). (plan: `…phase-2a-ir-refinement.md`)
- **Phase 2b** — emission: `phantasos cli build` emits a working Typer+Rich CLI with
  `set`/`del`/`show`, the `_generated/`-vs-hand-owned split, runtime dispatch, config/output.
  (plan: `…phase-2b-emission.md`, with an authoritative Hardening H1–H12 section)

State: **152 tests pass, ruff + mypy clean**, branch ~45 commits ahead of `main`.
`phantasos cli build prisma-browser` emits an installable `prisma-browser-cli` (48 commands)
that imports and runs (`--help` works). Real-SDK e2e tests exist
(`tests/test_cli_emitted_real.py`) and dispatch through the real facade (mocked only at
`facade.Client.from_env`).

## The generator at a glance (for re-orientation)

`src/phantasos/generator/cli/`: `introspect.py` (built SDK → `OperationInventory`) →
`classify.py` (`build_cli_ir` → typed `CliIR`) → `render_cli.py` (Jinja templates in
`templates/` → emit project) / `discover.py` (report + cli.yml stub). The emitted
`_generated/runtime.py` loads the typed IR from `ir.json` (via the emitted `spec.py`, a
drift-free copy of `ir.py`), picks a `MethodBinding` from supplied args, builds+wraps the body
model, and calls `facade.Client.from_env().<resource>.<method>`. CLI verbs map to SDK methods
via the aggregated IR; `cli.yml` carries per-product deltas.

## Phase 3 work, in recommended order

### 3a — Author `products/prisma-browser/cli.yml` (DO THIS FIRST)
The real build currently runs **CRUD-only and warns "16 unmapped ops"**. The generator
machinery for variants + overrides is built and tested; it just needs the per-product config.
- `phantasos cli discover prisma-browser --write-stub` → start from the stub.
- Add the `variants:` map for `applications.create_application`
  (`{custom: CustomApplicationInput, private: PrivateApplicationInput, non-web:
  NonWebApplicationInput, localdesktopcustom: LocalDesktopApplicationInput}`, `path_param: type`)
  so `set application <variant>` works via the real binary.
- Map (or `hide:`) the 16 non-CRUD ops (see 3b). Rebuild and exercise the real CLI end-to-end.
- No code change expected — this is product-config authoring + a live-validation pass.

### 3b — `request` namespace verb (non-CRUD actions)
~16 ops don't classify as CRUD: `suspend_*`, `force_reauth_*`, `revoke_*`, `publish_*`,
`archive_*`, `restore_*`, `resume_*`, `action_*`, `*_positions`. Spec calls for
`request <resource> <action>`. Needs: `cli.yml` `request:` mappings (already modeled in
`CliConfig`); `build_cli_ir` to emit `request`-verb commands from those mappings (currently it
`continue`s past `cfg.request` entries — see `classify.py`); runtime/templates to dispatch them
(they're mostly POST actions with a body or just an id). Add `request` to the emitted verb apps.

### 3c — `load` / `backup` verbs (per object-type)
`backup <object> --file f.yaml` (list → YAML) and `load <object> --file f.yaml [--dry-run]`
(YAML → create/update each). Per-object now; design the file format to extend to whole-tenant
later (spec decision). Reuses the runtime's set/show plumbing.

### 3d — `COMMANDS.md` command reference (deferred from 2b)
Generate markdown from the emitted app. Do it **subprocess-isolated** (don't mutate
`sys.path`/`sys.modules` in-process). Lowest-value/highest-fiddle — keep it simple.

### 3e — Dynamic (live-value) shell completion
e.g. `--id <tab>` lists real IDs via the API. Needs auth at completion time + caching. Static
completion (verbs/objects/flags/enum values) already ships.

### 3f — Dot-notation nested flags
Per-field overrides of JSON-string flags (`--risk.level high`), precedence over the JSON value.
(pydantic-settings does this; we deferred it.)

### 3g — Full phantasos-grade scaffold parity
The generated CLI is currently a lean project. Reuse `src/phantasos/scaffold/` + per-product
`overrides/` to emit CI/CD workflows, the mkdocs site + publish, release/audit/secrets/codeql,
pre-commit, dotfiles, LICENSE/CHANGELOG — matching the SDK. (This is the deferred "consistency"
enhancement.)

### 3h — SDK-side id-parameter harmonization (optional, SDK layer)
Tracked in `docs/TODO.md`. The CLI works today by detecting the id path-param per op; a
canonical `--id` in the SDK would simplify the classifier. Independent of the CLI.

## Known issues / tech debt to fix in Phase 3 (from review passes)

- **`bulk_create_*`/`bulk_delete_*` and any `list[Model]` request body are mis-introspected as a
  path param** (Task-4 `list[Model]` TODO in `introspect.py`). Bulk verbs (`set --bulk`) need
  `introspect` to detect `list[BaseModel]` bodies. Until then `bulk_*` commands are degraded.
- **Injected-option flag-name collision**: a body/query field literally named `output`/`all`/
  `verbose`/`dry-run`/`replace` collides with the injected Typer option at the *CLI-flag* level.
  `_py_name` only fixes the Python identifier, not the `--flag` name. Unlikely in prisma-browser;
  detect + rename the flag (e.g. prefix) when it occurs.
- **Path-wins flag dedup is aggressive in principle** (`render_cli._command_view`): safe here only
  because the sole collisions are the redundant `type` discriminator. A body field legitimately
  sharing a path-param name but carrying different data would be silently dropped. Generalize: the
  runtime should repopulate the body from the resolved value (it now does this for the variant
  discriminator — extend the idea if other collisions arise).
- **`patch` cannot send JSON `null` to clear a field** (all flags default `None` → dropped). Add a
  `--unset <field>` mechanism if needed.
- **`select_method_for_verb`** (classify.py) is now superseded by aggregation — decide delete vs
  keep.
- **`Override.variant`** is declared in `cliconfig.py` but unused by `build_cli_ir` — implement or
  remove.
- **Cosmetic:** emitted dir is `prisma_browser-cli` (package-derived, mixed `_`/`-`); prefer the
  distribution name (`prisma-browser-cli`) for the output dir in the `cli build` path math.
- **Body-field `--help`** comes from the model; path/query `--help` now comes from `Annotated`
  descriptions (H-fix in 2a) — verify completeness when COMMANDS.md lands.

## Process notes for whoever resumes (important)

- **Test env:** the repo `.venv` is on a filesystem that can't hold symlinks. Use
  `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …` (or `uv sync --all-groups`
  to (re)create it).
- **Git discipline:** subagents must NOT `git checkout`/`switch`/`reset` (a detached-HEAD incident
  occurred mid-Phase-2; recovered via `git checkout -B cli-generator`). Commit on the branch; use
  `git show <sha>:<path>` to view history.
- **Testing philosophy (per the user):** real-SDK e2e must mock only at the
  `facade.Client.from_env` boundary (a `MagicMock`/recorder), NEVER stub `rt._client` — this is
  what caught the 3 Phase-2b bugs the fixture/mock tests missed. Keep that discipline.
- **Workflow:** brainstorm if scope is fuzzy → `writing-plans` per sub-phase → subagent-driven
  execution (implementer + spec review + code-quality review per task) → review the highest-risk
  emitted code with a strong model and ALWAYS validate against the real SDK.
- `typer` is a dev dependency (for CliRunner + importing emitted code in tests); `rich`/`pyyaml`
  are present in the env. The generated CLI declares its own deps in its emitted `pyproject.toml`.

## Branch / finishing
The work is on `cli-generator` (not merged). When ready, use
`superpowers:finishing-a-development-branch`. Pre-existing unrelated working-tree changes
(deleted `docs/*.md`, modified `.gitignore`) were present at session start and are NOT part of
this feature — don't sweep them into a merge.
