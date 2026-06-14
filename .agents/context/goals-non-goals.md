# goals-non-goals

Validated against f5cf840 on 2026-06-14 · Purpose: what phantasos is for, and the boundaries it deliberately does not cross.

This frames scope so that design questions can be answered by "is this on the
path or off it?". The *why* behind several of these lines lives in
[decisions](decisions.md); the binding rules live in `CLAUDE.md`. (An earlier
architecture proposal framed scope as "arbitrary OpenAPI specs"; the goals below
supersede that framing.)

## Goals

- **Production-grade Python SDKs and CLIs for Palo Alto Networks products**,
  generated from their OpenAPI specs. PAN products are the scope and the thing the
  project is maintained to serve well.
- **Self-contained artifacts.** A generated SDK depends only on a small runtime set
  (`urllib3`, `python-dateutil`, `pydantic`, `typing-extensions`) and carries its
  own vendored component code — no dependency on phantasos itself. See
  [components](components.md).
- **Full production scaffolding.** The emitted project ships everything a real
  package needs: tests, CI/CD workflows, docs config, pre-commit, licence,
  changelog, and the rest — not just `models/` and `api/`. See
  [scaffold](scaffold.md).
- **Close OpenAPI Generator's gaps.** Real auth, pagination, and error handling;
  codegen-bug patches (apostrophe-enum, lenient str+int enums, oneOf first-match);
  generic spec preprocessing — the parts OAG does not give you. See
  [sdk-generator](sdk-generator.md).
- **Keep generated artifacts disposable and regenerable.** Every build regenerates
  the artifact wholesale; all durable customization lives in `products/<name>/`
  and `src/phantasos/scaffold/`, never in the artifact. See [index](index.md).

## Non-goals

- **General-purpose arbitrary-OpenAPI tooling.** PAN products are the scope. The
  generator's spec-agnostic implementation (pluggable components, no PAN
  hard-coding) is an engineering convenience, **not** a maintained promise to
  support arbitrary non-PAN specs. See
  [decisions](decisions.md#scope-is-palo-alto-networks-products-not-arbitrary-openapi).
- **A runtime or framework.** phantasos *generates standalone code*; it does not
  wrap, host, or run the SDKs and CLIs it produces. The artifact stands alone with
  no phantasos import.
- **Other target languages.** Python only. There is no goal to emit SDKs/CLIs in
  other languages.
- **A reimplementation of OpenAPI Generator.** phantasos *augments* OAG (runs the
  upstream jar, then patches and scaffolds around it); it does not replace its
  codegen. See
  [decisions](decisions.md#wrap-and-patch-openapi-generator-do-not-reimplement-it).

## Current scope facts (not commitments)

These describe what the shipped code happens to do today; they are observations,
not boundaries, and may change without being "scope creep":

- Generated SDKs are currently **synchronous**, built on `urllib3`. (Async is *not*
  declared out of scope — it simply is not what the current artifacts emit.)
- The CLI layer targets **Typer + Rich** for the generated command-line interface.
- The first product is **prisma-browser**; the implementation is spec-agnostic so
  additional PAN products plug in via their own `products/<name>/` directory.
