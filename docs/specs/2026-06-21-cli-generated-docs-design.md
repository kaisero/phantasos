# CLI generated docs — design spec

Status: **DESIGN COMPLETE (grilling done) — ready for planning**
Date: 2026-06-21
Branch: `feature/cli-docs`
Author: Oliver Kaiser (with Claude)

## Problem

The phantasos pipeline generates a per-product **SDK docs site** (config-gated
MkDocs-Material; shipped in #30/#33). The generated **CLI** has no equivalent: it
emits only a `README.md`, Rich `--help`, and `config show`, and the CLI scaffold
hardcodes `has_docs=False` ("docs are SDK-only", `generator/cli/scaffold_context.py:72`).

We want the pipeline to also generate a **CLI docs site** — a quickstart and a
command reference — mirroring the SDK docs' content and look, emitted into each
generated CLI project.

## Glossary

- **CLI docs site** — a standalone MkDocs-Material site emitted *into a generated
  CLI project* (its own `mkdocs.yml`, `docs/` tree, docs nox session, Pages
  workflow). Distinct from (a) phantasos's own user docs and (b) the per-SDK docs
  site. Never combined with the SDK site.
- **Command reference** — the centerpiece reference section: every CLI command,
  grouped per object, with flag tables and examples, rendered from the CLI IR.
- **CLI IR** — `CliIR` (`generator/cli/ir.py`), serialized to `_generated/ir.json`;
  per-`Command` carries `summary`/`description`, `path_params`/`body_flags`/
  `query_flags` (each `Flag` with `help`/`choices`/`required`/`py_type`/`kind`),
  `body_model`, `paginated`, `get_by_id_only`, `columns`, underlying `sdk_method`.
- **Showcase command** — (TBD) the single command used in the Quickstart's worked
  example.

## Decisions (resolved during grilling)

### D1 — Standalone CLI docs site, never combined
The CLI docs are a self-contained site emitted into the CLI project. No combined
SDK+CLI site. Keeps the two emitted artifacts independent; matches the existing
per-scaffold `has_docs` seam.

### D2 — Command reference is rendered from the CLI IR (not Typer help)
mkdocstrings (the SDK reference tool) is wrong here — the user surface is the
command tree, not a Python API. The IR already carries everything a reference
needs and is the same source of truth that drives the emitted `--help`, so an
IR-driven reference cannot drift from the real CLI. Rejected: Typer→markdown /
`--help` capture (flat, needs the CLI importable at docs build, captures Rich
formatting, low structural control).

### D3 — Generate-time static rendering (not mkdocs-gen-files)
A framework-side CLI docs stage (analogous to `sdk/docs.py`) shapes a docs context;
Jinja templates render concrete `.md` files (guides *and* command reference) into
the CLI project's `docs/` during `phantasos cli build`. MkDocs then builds plain
static markdown. The SDK uses gen-files only because mkdocstrings needs live
objects — that reason doesn't apply to an IR→markdown reference. We mirror the
SDK's content and look, not its mechanism.

### D4 — Page set
1. Home (`index.md`) — what the CLI is, install, links, short verbs explainer
   (create/update/delete/show/request). No Architecture page (SDK-internals only).
2. Quickstart — install → configure credentials → first commands → output formats.
3. Command Reference — per-object pages; every command with flag tables + examples.
4. Guides:
   - Authentication & environments (credentials, named environments, config
     layering, `config set/show/unset`)
   - Output & formatting (`--output`, `--columns`, pager)
   - Pagination (`--limit` / `--all`)
   - Error handling & diagnostics (exit codes, error taxonomy, `--verbose`,
     `show cli history`, log files)

### D5 — Dedicated `docs:` block in `cli.yml`
CLI docs are gated by their own `docs:` block in `cli.yml` (its own model, e.g.
`CliDocsConfig`), independent of the SDK's `sdk.yml` `docs:` block. The CLI
scaffold's `has_docs` flips from the hardcoded `False` to `cfg.docs is not None`.
A product can enable CLI docs and SDK docs independently.

### D6 — Showcase via required `showcase_object` (+ optional `showcase_variant`)
`cli.yml` `docs:` carries a required `showcase_object` (an object key), validated
against the CLI IR's objects (build fails loudly on unknown name), plus optional
`showcase_variant` for oneOf creates. The Quickstart auto-derives that object's
verbs (`show` preferring list else get-by-id; `create`; and `update`/`delete`
where present). Rejected: auto-selecting the showcase object (explicit + validated
is the SDK precedent).

### D7 — CLI examples: required-only, synthesized in `cli/examples.py` (no sharing)
Worked examples are command invocation strings synthesized from the IR `Flag`s —
required body flags + required path params only (full detail lives in the flag
table). Per-flag values come from a CLI-specific value strategy living in
`generator/cli/examples.py`. **The value strategy is intentionally NOT shared with
`sdk/examples.py`** — the user wants clear separation of duty between the SDK and
CLI generator paths, accepting duplicated value logic. Flag kinds map to CLI
syntax (`json` → `--field '{...}'`, `file` → `--file ./path`, oneOf → the variant
subcommand). Optional per-command verbatim overrides via a `docs.examples` map in
`cli.yml` keyed by command key (`verb:object[:variant|action]`).

### D8 — Guide gating
Always: Home, Quickstart, Command Reference, Output & formatting, Error handling &
diagnostics. Conditional: Authentication & environments (only when the CLI has
credentials / an auth component), Pagination (only when any command is paginated).

### D9 — Command reference: per-object pages, full-surface tables
One reference page per object (all of that object's verbs together). Per command:
usage line, summary + description, flag tables grouped to match the Rich `--help`
panels (Path / Body / Filters / Pagination / Common; row = name, type, required,
choices, help) showing the **full** flag surface, one synthesized required-only
example, and a default-columns note for list/show. Rejected: one-page-per-command
(too fine), single flat page (too coarse).

### D10 — Scaffold seam (VERIFIED FACT informing the design)
`src/phantasos/scaffold/` is **fully shared** by SDK and CLI builds (same
`render_scaffold`, same tree; templates self-skip when they render to whitespace).
Gating is by `has_*` flags; **there is no SDK-vs-CLI discriminator**, and every
existing doc template is hardcoded SDK-flavored (teaches `client.<object>`,
introspects `_WRAPPERS`/`models/`). Therefore flipping `has_docs=True` for the CLI
would wrongly emit SDK doc pages. Implication resolved in D11.

### D11 — Seam: CLI owns content (from IR); dedicated `cli_docs` flag; shared infra branches
- The CLI generator owns all CLI-flavored doc **content** — the doc pages *and* the
  CLI's `mkdocs.yml` — rendered from the `CliIR` (a new docs pass in `render_cli`,
  regenerated every build), living under `generator/cli/` (e.g. `templates/docs/`).
  These never reuse the SDK doc templates (no `client.<object>`, no mkdocstrings,
  no `_WRAPPERS`). The CLI `mkdocs.yml` is plain static markdown (no
  `mkdocstrings`/`gen-files`/`literate-nav`/`griffe-pydantic`).
- A dedicated **`cli_docs`** scaffold-context flag (set when `cli.yml` has a `docs:`
  block) drives CLI docs. The SDK's `has_docs` stays `False` for CLI builds, so **no
  SDK doc template ever fires for the CLI** — the SDK doc templates are not touched.
- Generic, content-agnostic infra stays shared with a minimal `cli_docs` branch: the
  `pyproject.toml` docs dependency group (CLI = just `mkdocs-material`), the
  `noxfile.py` `docs`/`docs-serve` sessions, and the GitHub Pages workflow.
- Rejected: branching the shared SDK doc templates on an `is_cli` flag (mixes
  CLI-flavored content into SDK templates; violates separation of duty).

### D12 — Build/test/CI wiring mirrors `sdk-docs` 1:1
- New `cli-docs` nox session (per-product, enrolled via `nox.toml [cli-docs]`):
  `phantasos cli build <product>` (needs the product SDK importable, like
  `sdk-docs`) → `mkdocs build --strict` in the emitted CLI → assert the
  command-reference pages exist + per-product content guards. Kept out of
  `nox.options.sessions`.
- Framework unit tests on the emitted markdown (`test_cli_docs_emitted.py` mirroring
  `test_sdk_docs_emitted.py`), driven off the `fakesdk` fixture (offline, no real
  product).
- CI job running `nox -s cli-docs` (parallel to `sdk-docs`/`cli-smoke`).
- GH-Pages workflow emitted into the CLI project (gated on `cli_docs`).
- Note: the `mkdocs build` step needs only `mkdocs-material` (markdown is rendered at
  generate time, D3); only `phantasos cli build` needs the SDK.

### D13 — Explicit IR-generated nav
The CLI `mkdocs.yml` `nav:` is written explicitly at generate time from the IR
(Home, Quickstart, the applicable guides, one Command-Reference entry per object).
No `literate-nav`/`gen-files`. Keeps the docs dependency group to `mkdocs-material`
and the nav deterministic/testable.

### D14 — `site_name` default
Optional `site_name` in `cli.yml` `docs:`. Default = `"<product title> CLI"` when the
product has a human title, else the distribution name.

### D15 — README stays the PyPI/repo landing
Keep the emitted `README.md` as the concise repo/PyPI face; when `cli_docs` is
enabled, add a short "Documentation" link section pointing at the docs site (a
minimal `cli_docs` branch in `README.md.jinja`). Not deeply synced with the site.

### D16 — Errors & diagnostics guide: static prose + one IR-driven subsection
VERIFIED: the emitted CLI has **no exit-code enum and no error taxonomy** — exit
codes are inline literals; the only IR-driven error surface is `error_envelope`.
So the guide is:
- Mostly **static prose** documenting real behavior: exit codes `0` (success),
  `1` (operation/server/auth/IO failure), `2` (bad input / usage; also Typer's
  own `2`); the three diagnostic levels (`✖`/`⚠`/`ℹ` on stderr, auto-plain when
  piped/`NO_COLOR`); `--verbose` → full traceback; `--quiet` → errors-only;
  `show cli history` (recorded fields; auth headers excluded; `--entry` JSON);
  rotating gzipped JSONL logs (location, `logging.level`/`file`, env vars);
  `config init/show/set/unset`.
- **One IR-driven subsection** rendered from `ir.error_envelope` — how *this
  product's* API error bodies become a headline (wrappers / error_field /
  message_field / fallback keys).
- A cheap **drift-guard test** in the framework greps the emitted runtime for
  `code=`/`SystemExit(` and asserts only `1`/`2` appear, so the static exit-code
  table cannot silently drift.
- **Out of scope:** refactoring error handling (no `ExitCode` enum, no taxonomy
  build) — we document what exists.

### D17 — Rollout: enable for prisma-browser, adem, posture
Validate against **three different real CLIs**. Each product gets a `docs:` block in
its `cli.yml` with a chosen `showcase_object`, and all three are enrolled in the
`cli-docs` gate with content assertions. Other products opt in later.
**Prerequisite/risk:** each product must be `phantasos cli build`-able. **adem is
flagged** — memory `pr33-ci-wrapper-branch-gaps` records adem non-CRUD ops as
unbuildable under the clean-wrapper classifier; verify `phantasos cli build adem`
succeeds (may need `cli.yml` `hide`/`request` for its non-CRUD ops) **before**
enrolling it. This is a plan prerequisite, not a blocker for the framework work.

## Non-goals

- No combined SDK+CLI site (D1).
- No refactor of error handling — no `ExitCode` enum, no taxonomy (D16).
- No mkdocstrings/autodoc of CLI internals (D2).
- No runtime `model-describe` flag — the reference's full-surface flag tables cover
  the static need (D9); the runtime flag remains a separate future effort.
- No deep README↔site content sync (D15).
- The CLI docs value strategy is **not** shared with `sdk/examples.py` (D7).

## Implementation outline (seam / module map)

CLI-owned (separation of duty):
- `generator/cli/cliconfig.py` — add `CliDocsConfig` (`showcase_object` [required],
  `showcase_variant`, `site_name`, `examples` map) + `docs` field on `CliConfig`;
  IR-validate `showcase_object` (fail loud on unknown).
- `generator/cli/docs.py` (NEW) — build the CLI docs context from `CliIR`: showcase
  derivation, per-object command grouping, guide-gating flags (auth/pagination),
  the `error_envelope` subsection.
- `generator/cli/examples.py` (NEW) — CLI value strategy + invocation renderer
  (duplicated by design; flag kinds → CLI syntax).
- `generator/cli/templates/docs/*.jinja` (NEW) — `index`, `quickstart`, per-object
  command reference, guides (auth / output / pagination / errors), and a CLI
  `mkdocs.yml.jinja` with an explicit IR-generated `nav:`.
- `generator/cli/render_cli.py` — new docs render pass (from context; regenerated
  every build, like `_generated/`).
- `generator/cli/scaffold_context.py` — set `cli_docs = cfg.docs is not None`
  (keep `has_docs=False`).

Shared scaffold (minimal `cli_docs` branches only):
- `pyproject.toml.jinja` — CLI docs dependency group = just `mkdocs-material`.
- `noxfile.py.jinja` — emit `docs`/`docs-serve` sessions also when `cli_docs`.
- `.github/workflows/docs.yml.jinja` — emit Pages workflow also when `cli_docs`.
- `README.md.jinja` — add a "Documentation" link when `cli_docs`.

Pipeline / tests:
- `noxfile.py` — new `cli-docs` session (per-product, enrolled via `nox.toml
  [cli-docs]`, strict build + content asserts); kept out of default sessions.
- CI — `cli-docs` job.
- `tests/test_cli_docs_emitted.py` (NEW, `fakesdk` fixture) — assert emitted
  markdown: pages present, flag tables, synthesized examples, nav, guide gating.
- Exit-code drift-guard test (greps emitted runtime; only `1`/`2` allowed).

## Risks & prerequisites

- **adem CLI buildability** (D17) — verify before enrolling.
- **Large command trees** → big reference pages; per-object grouping mitigates.
- **Exit-code drift** between static docs table and inline literals → drift-guard
  test mitigates.
- **Showcase selection** per product must pick an object with a `create` (and
  ideally `show`) so the Quickstart is meaningful.

## grill-with-docs artifacts

- **Glossary** — maintained in the Glossary section of this spec. (The repo's
  convention is `.agents/context/` deep-dives + `docs/specs/`; no root `CONTEXT.md`
  is introduced. On implementation, the CLI-generator deep-dive
  `.agents/context/cli-generator.md` gains a "docs sub-stage" narrative.)
- **ADR** — `docs/adr/0001-cli-docs-ir-driven-generate-time.md` records the central
  divergence from the SDK docs system (IR-driven, generate-time, CLI-owned).

## Next steps (user's standard flow)

1. **Plan** (writing-plans) — decompose into TDD-able tasks with review checkpoints.
2. **2× expert subagent reviews** of the plan.
3. **subagent-driven-development** execution.
- Command reference nav / per-object page structure for large command trees.
- Build/CI wiring (nox `cli-docs` session, Pages workflow, flipping `has_docs`).
- Reference depth (body-flag field surface; relationship to the planned
  model-describe flag).
