# phantasos

> Generate native, self-contained Python SDKs and CLIs from OpenAPI specs. This
> is the read-first map for coding agents working in-repo: the system model and
> where each subsystem is documented. Load only the deep-dive you need.

## System technical design

phantasos is a two-stage code generator. Stage one turns an OpenAPI spec into a
standalone Python SDK; stage two introspects that built SDK to emit a matching
Typer CLI. Both stages are driven by the host CLI `phantasos` (`src/phantasos/cli.py`,
a Typer app): `phantasos sdk build <product>` produces the SDK, then
`phantasos cli build <product>` produces the CLI (`phantasos cli discover` prints
the operation→command classification table and an optional `cli.yml` stub). Each
emitted project is standalone, depending only on a small urllib3-based runtime
set (`urllib3`, `python-dateutil`, `pydantic`, `typing-extensions` — see
`productconfig._BASE_DEPS`).

Three layers, kept strictly separate:

- **Framework code** — `src/phantasos/`. The generator itself. Version-controlled.
- **Generated artifact** — the emitted SDK/CLI project (written to the product's
  `output` dir, outside this tree). A pure build artifact: regenerated wholesale
  on every build, never hand-edited.
- **Product config** — `products/<name>/`: `openapi.yml` (the spec), `sdk.yml`
  (SDK build config), optional `cli.yml` (CLI command mapping), `overrides/`
  (per-product scaffold templates; `README.md.jinja` is required), and optional
  `hooks.py` (Python preprocess/patch hooks). Version-controlled.

Control/data flow. The host CLI loads a product via
`phantasos.productconfig.load_product` (parses + validates `sdk.yml` into a
`LoadedProduct`, resolving auth/pagination/errors/facade/retry component blocks
and building the Jinja `context`). `sdk build` then calls
`phantasos.generator.sdk.build.build`, which orchestrates the SDK pipeline:
preprocess the spec → run OpenAPI Generator (provisioning a pinned JRE +
generator jar on first use) → apply codegen-bug patches → vendor component
templates into `<package>/extras/` → render the scaffold → smoke import-check.
`cli build` introspects the built SDK (`generator.cli.introspect`), classifies
operations into a command IR (`generator.cli.classify.build_cli_ir`), then renders
the CLI via `generator.cli.render_cli.render_cli` plus the shared scaffold.

Repo map (`src/phantasos/`):

- `cli.py` — host Typer app (`sdk build`, `cli discover`, `cli build`).
- `productconfig.py` — load/validate `sdk.yml` → `LoadedProduct` + Jinja context.
- `config.py` — pydantic component models (auth/pagination/errors/facade/retry).
- `scaffold.py` — renders the project scaffold (built-in + product overrides).
- `scaffold/` — built-in scaffold templates (pyproject, noxfile, workflows, …).
- `generator/sdk/` — the SDK build pipeline.
- `generator/cli/` — the CLI generator (introspect → classify → render).

Hard invariants:

- The generated SDK/CLI is **disposable** — fully regenerated each build; nothing
  durable lives in it. Never hand-edit it.
- The **only** version-controlled customization surfaces are `products/<name>/`
  and `src/phantasos/scaffold/`.

## Subsystem deep-dives

- [product-config](product-config.md): `products/<name>/` anatomy + how `productconfig.load_product` validates `sdk.yml` into a `LoadedProduct`.
- [sdk-generator](sdk-generator.md): the SDK build pipeline (preprocess → generate/OAG → patches → vendor → scaffold → smoke).
- [components](components.md): the vendored, Jinja-templated components (auth/pagination/errors/facade/retry) rendered into `extras/`.
- [cli-generator](cli-generator.md): the CLI generator (introspect → classify → render) + the layered generated-CLI config.
- [scaffold](scaffold.md): the shared scaffold engine (built-in templates vs product overrides, same-path-wins).
- [phantasos-cli](phantasos-cli.md): the host CLI surface (`phantasos sdk build` / `cli discover` / `cli build`).
- [harness-and-testing](harness-and-testing.md): the quality harness (freeze + fast-gate hooks, `nox -s gate`/`live`, frozen oracle).
- [release-workflow](release-workflow.md): branching + version-driven release automation.

## Cross-cutting

- [decisions](decisions.md): the design-decision log + rationale (the WHY, incl. evolutions from `ARCHITECTURE.md`).
- [goals-non-goals](goals-non-goals.md): what phantasos is and isn't (Palo Alto Networks-focused).

## Rules

The binding rules (test policy, branching/release, the config-adding recipe) live
in `CLAUDE.md` at the repo root — this set explains mechanism and rationale, not rules.
