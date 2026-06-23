# 1. CLI docs are IR-driven, generate-time, and CLI-owned (not a copy of the SDK docs system)

Date: 2026-06-21
Status: Accepted
Context spec: `docs/specs/2026-06-21-cli-generated-docs-design.md`

## Context

The phantasos pipeline already generates a per-product **SDK docs site** (#30/#33):
a config-gated MkDocs-Material site whose API reference is produced by
**mkdocstrings** autodoc, generated at **mkdocs-build time** via `mkdocs-gen-files`
+ `literate-nav` (because mkdocstrings needs the live Python objects), using doc
templates that live in the **shared** `src/phantasos/scaffold/` tree.

We now want an equivalent **CLI docs site**. The obvious path is "do exactly what
the SDK does." But the CLI is a different kind of artifact: its user-facing surface
is a *command tree* (Typer + Rich), not a Python API, and a rich **`CliIR`**
(`generator/cli/ir.py`) already describes every command, flag, help string, choice,
and body model. The shared scaffold doc templates are also hardcoded SDK-flavored
(they teach `client.<object>.<verb>(...)` and introspect `_WRAPPERS`), and there is
no SDK-vs-CLI discriminator in the scaffold context.

## Decision

The CLI docs system deliberately **diverges** from the SDK docs system on three axes:

1. **IR-driven, not autodoc.** The command reference is rendered from `CliIR`, not
   from mkdocstrings. The IR is the same source of truth that drives the emitted
   `--help`, so the reference cannot drift from the real CLI.
2. **Generate-time static rendering, not `gen-files`.** A framework-side CLI docs
   stage shapes a context and Jinja renders concrete `.md` files (guides *and*
   reference) during `phantasos cli build`. MkDocs then builds plain static
   markdown. The SDK needs `gen-files` only because mkdocstrings needs live
   objects — that reason does not apply to an IR→markdown reference.
3. **CLI-owned content + a dedicated `cli_docs` flag.** CLI-flavored content (doc
   pages and the CLI `mkdocs.yml`) lives in the CLI generator and is rendered from
   the IR; it never reuses the SDK doc templates. A dedicated `cli_docs` scaffold
   flag gates it, and the SDK's `has_docs` stays `False` for CLI builds, so **no SDK
   doc template ever fires for the CLI**. Only content-agnostic infra (docs
   dependency group, `docs` nox session, Pages workflow) stays shared, behind a
   minimal `cli_docs` branch.

## Alternatives considered

- **Mirror the SDK 1:1** (mkdocstrings + `gen-files` + `literate-nav`, branch the
  shared SDK doc templates on an `is_cli` flag). Rejected: mkdocstrings would
  document internal command modules, not the command tree; `gen-files` adds moving
  parts with no benefit here; and branching the shared SDK templates mixes
  CLI-flavored content into them, cutting against the project's preference for clear
  separation of duty between the SDK and CLI generator paths.
- **Drive the reference from Typer's own `--help`/`typer utils docs`.** Rejected:
  flat output, requires the CLI importable at docs-build time, captures Rich
  formatting, and gives little structural control.

## Consequences

- The CLI docs build needs only `mkdocs-material` (no mkdocstrings/gen-files/
  literate-nav/griffe). Nav is written explicitly from the IR.
- The CLI value strategy for synthesized examples is duplicated in
  `generator/cli/examples.py` rather than shared with `sdk/examples.py` (a
  deliberate separation-of-duty trade-off).
- The two doc systems look similar to *users* but differ mechanically; maintainers
  must not assume the SDK docs mechanism applies to the CLI. The CLI-generator
  deep-dive (`.agents/context/cli-generator.md`) should explain the docs sub-stage.
- Anything not in the IR (e.g. exit-code literals) cannot be rendered and is handled
  as static prose guarded against drift by a test.
