# decisions

Validated against f5cf840 on 2026-06-14 · Purpose: the load-bearing design decisions behind phantasos — what was chosen, why, and what was rejected.

This is a decision log, not a how-to. Each entry records a choice that shaped the
system, the reasoning, the rejected alternative where it is instructive, and a
pointer to the deep-dive or spec that elaborates it. The **binding rules** (test
policy, branching/release, the config-adding recipe) live in `CLAUDE.md` — this
file explains *why*, not *what you must do*.

A note on `docs/ARCHITECTURE.md`: it is the original architecture-review proposal
and is now **stale** on two points — the repo layout it sketches, and its
"arbitrary OpenAPI specs" framing. Where it conflicts with the entries below, the
entries (which reflect the maintained intent and the shipped code) win. The
conflicts are flagged as *evolutions* so the history stays legible.

---

## Configuration is declarative data (`sdk.yml`), not executable code

A product is described by a reviewable YAML file (`sdk.yml`), not by a per-spec
Python module. Config should be **data**: a YAML file can be diffed and reviewed
at a glance, cannot run arbitrary logic during a load, and constrains a product
author to a validated schema. The rare cases that genuinely need code — spec
preprocessing, codegen patches — go in an explicit, narrow `hooks.py` whose surface
is small and obvious, rather than being smeared through the config. This extends
the harness's anti-arbitrary-code ethos to the configuration layer.

- **Rejected:** the original per-spec Python module from `ARCHITECTURE.md` §1/§5
  (`CONFIG = SdkConfig(...)` plus free-form `preprocess`/`patch` functions). It
  made every config an executable program — harder to review, trivially able to
  do anything.
- *Evolution from `ARCHITECTURE.md`.* See [product-config](product-config.md).

## Scope is Palo Alto Networks products, not arbitrary OpenAPI

The real, maintained goal is generating SDKs and CLIs for **Palo Alto Networks
products** from their OpenAPI specs. `ARCHITECTURE.md` framed the project as a
generator for "arbitrary OpenAPI specs"; that framing is superseded. The nuance
worth preserving: the *implementation* is deliberately spec-agnostic — pluggable
components, generic spec transforms, no PAN-specific hard-coding in the generator
core — but that is an engineering convenience, not a promise. Supporting
arbitrary **non-PAN** specs is explicitly not a maintained goal; do not contort
the design to serve one.

- *Evolution from `ARCHITECTURE.md`.* See [goals-non-goals](goals-non-goals.md).

## Components are vendored and templated, not a runtime dependency

The reusable behaviours (auth, pagination, errors, facade, retry) are Jinja
templates rendered at build time into the generated package's `extras/`
directory. The emitted SDK therefore carries its own copy of this code and
imports it directly — it has **no dependency on phantasos at all**, only on a
small runtime set (`urllib3`, `python-dateutil`, `pydantic`, `typing-extensions`;
see `productconfig._BASE_DEPS`). A user installs the SDK, not the generator.

- **Rejected:** shipping components as an importable runtime library the SDK
  depends on. That would couple every generated SDK to a phantasos release and to
  phantasos's own dependency tree.
- **Cost (accepted):** component code lives in `.jinja`, not directly importable,
  so it is covered by template-render tests (`ARCHITECTURE.md` §8). See
  [components](components.md).

## Wrap and patch OpenAPI Generator, do not reimplement it

phantasos runs the upstream OpenAPI Generator (OAG) jar — provisioning a pinned
JRE and jar on first use — and then *augments* it: generic spec preprocessing
before the run, codegen-bug patches after it (apostrophe-enum re-quote, lenient
str+int enums, oneOf first-match), and a vendored component + scaffold layer
around the result. OAG already handles the enormous surface of OpenAPI → Python
model/api codegen; rebuilding that would be a multi-year sink for no gain.

- **Rejected:** a from-scratch codegen engine. phantasos's value is the gaps OAG
  leaves (auth, pagination, errors, scaffolding, bug patches), not the codegen
  OAG already does. See [sdk-generator](sdk-generator.md).

## The generated artifact is disposable and never hand-edited

The emitted SDK/CLI project is a pure build artifact: every file in it — tests,
`pyproject.toml`, workflows, `README.md`, the package code — is regenerated
wholesale on every build. The only version-controlled customization surfaces are
`products/<name>/` and `src/phantasos/scaffold/`. Nothing durable lives in the
artifact, so nothing can be lost across regenerations, and "rebuild from scratch"
is always safe.

- **Why it matters:** it makes "regenerate freely" a guarantee rather than a hope,
  and it is the property the whole two-stage pipeline leans on. The CLI applies the
  same rule with a narrow exception — a hand-owned `main.py`/`custom/`/`hooks.py`
  emitted *once* and never overwritten, layered on top of a disposable
  `_generated/`. See [index](index.md) and
  [cli-generator](cli-generator.md).

## Pluggable components, selected per product; build only what is needed

Components are opted into per product via `sdk.yml`; a product builds only the
behaviours it selects. The interface set (auth / pagination / errors / facade /
retry) is deliberately kept minimal and is not over-abstracted ahead of demand.

- **Rationale:** `ARCHITECTURE.md` §8 names "over-abstraction before a 2nd spec"
  as the top risk. The mitigation is to build only what the current product needs
  and revisit the contracts when a genuinely different spec forces the question —
  not to speculatively generalise. See [components](components.md) and
  [product-config](product-config.md).

## Independent semver per generated SDK

Each generated SDK carries its own hand-bumped semantic version, independent of
phantasos's version and of the source spec's version. The spec, framework, and
jar versions used for a build are recorded as provenance (`_about.py`) in the
artifact.

- **Rationale:** a generated SDK's public API changes on its own cadence (a spec
  revision, a component fix); tying its version to the generator's would either
  over- or under-signal change to its consumers. `ARCHITECTURE.md` §1. See
  [sdk-generator](sdk-generator.md).

## Two-stage pipeline: build the SDK first, then introspect it for the CLI

Generation is two stages. Stage one turns a spec into a standalone SDK. Stage two
generates the matching Typer + Rich CLI by **introspecting the built SDK** —
walking its facade and `*Api` classes, resolved type hints, and pydantic field
metadata — not by re-reading the OpenAPI spec.

- **Rejected:** generating the CLI directly from the spec in parallel with the
  SDK. Introspecting the built SDK means CLI commands map 1:1 to real SDK calls
  with no hand-maintained name-mapping layer, and the CLI cannot drift from the
  SDK it wraps. The same typed-IR is used for both rendering and `cli discover`,
  so generation and discovery cannot drift from each other either. See
  [cli-generator](cli-generator.md) and the
  [CLI generator design](../../docs/specs/2026-06-09-cli-generator-design.md).

## Host-CLI structure: `sdk`/`cli` sub-apps over a shared generator package

The host CLI is a Typer app with `sdk` and `cli` sub-apps (`phantasos sdk build`,
`phantasos cli discover`, `phantasos cli build`). SDK-generation logic lives under
`generator/sdk/`, the CLI generator under `generator/cli/`, and the shared infra
(`scaffold`, `productconfig`, `config`) stays top-level so both stages reuse it.

- **Rationale:** symmetry between the two stages and one shared scaffold engine.
  The restructure preserved every behaviour, message, and exit code. See the
  [package + CLI restructure design](../../docs/specs/2026-06-12-sdk-generator-package-and-cli-restructure-design.md)
  and [phantasos-cli](phantasos-cli.md).

## An autonomous quality harness enforced by deterministic hooks, not prose

Because phantasos is developed mostly unattended, two orthogonal failure modes
threaten it: **green-but-fake tests** (the agent games its own success criteria)
and **unvalidated assumptions** about how the real API behaves. The chosen
controls are *deterministic hooks* plus a *frozen oracle*, not conventions the
model can rationalise past: a freeze hook denies edits to protected paths (fails
**closed**), a fast-gate hook blocks a turn while the offline gate is red or a
frozen path is dirty (fails **open**, never deadlocking the loop), and a live CRUD
round-trip through a generated SDK validates against the real tenant at phase
boundaries.

- **Rejected:** prose-only conventions in `CLAUDE.md`. The research backing the
  design concluded that for an unattended loop the critical controls must be
  mechanical. The asymmetry (freeze closed, gate open) is deliberate.
- See [harness-and-testing](harness-and-testing.md) and the
  [harness design](../../docs/specs/2026-06-10-autonomous-harness-thin-slice-design.md).

## Version-driven release on `main`; squash to `develop`, merge-commit to `main`

A landed `version` bump on `main` is what publishes — the release workflow keys
the published version and its `## [X.Y.Z]` notes off `pyproject.toml`. Feature
work squash-merges into `develop` (which never publishes); `develop` reaches
`main` only via a merge commit at release time.

- **Rationale:** the version is the single source of truth, so publishing is an
  explicit act (a deliberate bump on the one publishing branch) rather than an
  accident of merging. Squash-into-`develop` keeps history clean; merge-commit
  `develop → main` keeps the two branches from diverging so the next release PR
  stays clean. The exact rules are in `CLAUDE.md`. See
  [release-workflow](release-workflow.md).
