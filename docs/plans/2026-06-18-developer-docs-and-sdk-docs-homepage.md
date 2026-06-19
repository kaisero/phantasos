# Plan: Developer docs page + SDK-docs homepage/authoring coverage

**Date:** 2026-06-18
**Scope:** Documentation only (no code changes). Four files touched.
**Validation gate:** `uv run nox -s docs` (strict mkdocs build) must pass.

## Goal

1. Add a published **Development** page covering Git branching, Test Setup, CI/CD,
   and a getting-started for nox — in simple, clear, contributor-facing language.
2. Document the (currently undocumented) generated-SDK docs feature: a short
   teaser on the mkdocs **homepage** plus a full `docs:` field reference in
   **authoring.md**.

## Audience split

- `development.md` → people **contributing to phantasos itself**.
- The homepage teaser + authoring `docs:` section → people **authoring a product**
  whose generated SDK should ship its own docs site.

---

## Verified facts (read from the code, not assumed)

- **Emission gating:** the SDK docs scaffold is emitted **only when the `docs:`
  block is present** — `build.py:96` (`if loaded.config.docs is not None:`) and the
  `has_docs` context flag (`productconfig.py:249`). Confirmed.
- **`docs:` fields** (`productconfig.py:64-72`, `DocsConfig`):
  - `showcase_resource: str` — **required**; the resource whose CRUD drives the
    showcase examples.
  - `showcase_variant: str | None` — optional; selects a synthesis variant for the
    example bodies.
  - `site_name: str | None` — optional; defaults to the project `distribution`.
  - `operations: {create,read,list,update,delete}` — optional per-verb override of
    which SDK method maps to each CRUD slot (`DocsOperations`).
  - `examples: {create,read,list,update,delete}` — optional per-slot **verbatim**
    override of the generated example code block (`DocsExamples`).
  - Real-world minimal example in the repo: `products/prisma-browser/sdk.yml`
    uses just `docs:\n  showcase_resource: applications`.
- **Two distinct "docs" workflows — do NOT conflate them:**
  - The **generated SDK** ships its own `noxfile.py` with `docs` / `docs-serve`
    sessions and its own `.github/workflows/docs.yml` (gated on `has_docs`). The
    SDK *consumer/author* builds the SDK's site with `uv run nox -s docs` **from
    inside the generated SDK directory** (or `docs-serve` for live reload).
  - phantasos's own `nox -s sdk-docs` session is the **integration check** that
    builds the prisma-browser SDK + its docs end-to-end (`mkdocs build --strict`),
    needs JRE + network, and is NOT in the default session list.
  - => Homepage teaser shows the author workflow: add `docs:` → `phantasos sdk
    build <product>` → the generated SDK has a docs site (`nox -s docs` inside it).
    The `sdk-docs` session is mentioned as phantasos's own integration test, not as
    the author's primary command.
- **phantasos repo nox sessions** (12, from `noxfile.py` docstrings):
  `lint`, `type_check`, `tests` (3.11–3.14 matrix, coverage `fail_under`), `gate`
  (fast offline ruff+mypy+pytest; Stop-hook), `context` (regen `.agents/context`
  blocks), `audit` (pip-audit; online), `docs` (strict mkdocs build), `docs-serve`,
  `cli-smoke` (generate→clean-venv install→run), `smoke` (build example SDKs; JRE
  +network), `live` (real-tenant CRUD; needs creds, skips without), `sdk-docs`
  (integration; JRE+network). Default `uv run nox` runs: lint, type_check, tests,
  cli-smoke, docs.
- **CI workflows** (6, from `.github/workflows/`):
  - `ci.yml` — push to main/develop + all PRs: lint+type-check, tests matrix,
    docs (strict), cli-smoke, smoke. Mirrors the nox sessions.
  - `docs.yml` — push to main: build + deploy site to GitHub Pages.
  - `release.yml` — push to main: detect an unreleased `version` bump → publish to
    PyPI + GitHub Release.
  - `codeql.yml` — push/PR (main, develop) + weekly: CodeQL security analysis.
  - `audit.yml` — push to main + PR + weekly: pip-audit dependency CVE scan.
  - `secrets.yml` — push to main + PR + weekly: Gitleaks secret scan.

---

## File 1 (new): `docs/development.md`

Published page, simple/clear language. Sections:

### Development
Intro: who this page is for (contributors), and the one rule — the checks you run
locally are the same ones CI runs (via nox).

### Git branching
Contributor-focused subset only:
- Two long-lived branches: `develop` (integration) and `main` (released).
- Everyday flow: branch off `develop`; name it `feature/<slug>` or
  `bugfix/<slug>`; open a PR with `gh pr create --base develop`; it's
  **squash-merged**; record user-facing changes under `## [Unreleased]` in
  `CHANGELOG.md`.
- One-line note: "Cutting releases and hotfixes is a maintainer-only flow — see
  `CLAUDE.md` for the full procedure." (No diagram; no release machinery.)

### Test setup
- Where tests live (`tests/`), pytest is the runner.
- How to run: `uv run nox -s tests` (full matrix + coverage `fail_under`), or
  `uv run nox -s gate` for the fast offline loop, or plain `uv run pytest` for an
  ad-hoc subset.
- Python matrix: 3.11–3.14.
- Test tiers (smallest → largest): offline unit/behavioral suite → `cli-smoke`
  (generate a CLI, install into a clean venv, run it) → `smoke` (build the example
  SDKs end-to-end) → `live` (CRUD against a real tenant; skips without creds).
- Test policy (human-relevant): prefer real dependencies; never mock the system
  under test; show real command output before claiming a pass; "frozen oracles"
  are human-owned and never edited to make work pass.
- Pointer: "These are enforced automatically by the agent harness — see
  `CLAUDE.md` / `.claude/harness.toml` for the mechanics."

### CI/CD pipeline
Narrative mental model first:
- On every PR: `ci.yml` runs the same nox sessions you run locally (lint,
  type-check, tests matrix, strict docs build, cli-smoke, smoke).
- On merge to `main`: docs deploy to GitHub Pages; a landed `version` bump
  auto-publishes to PyPI + a GitHub Release.
- Continuously/weekly: security scans (CodeQL, pip-audit, Gitleaks).

Then a compact reference **table** of all 6 workflows: | Workflow | Trigger |
What it does |.

### Getting started with nox
- One command runs the default gate: `uv run nox`.
- `uv run nox -l` lists everything (self-documenting).
- Full reference **table** of all 12 sessions: | Session | What it does | When to
  run |. Flag the heavy opt-in ones (`smoke`, `live`, `sdk-docs`, `audit`) with
  their prerequisites (Java auto-provisioned / network / live creds / online).
- Clean happy-path commands only — no `UV_PROJECT_ENVIRONMENT` / `NOX_ENVDIR`
  (those live in `CLAUDE.md` for sshfs checkouts).

## File 2: `mkdocs.yml`
Add `- Development: development.md` to `nav`, **last** (after CLI reference).

## File 3: `docs/index.md`
Add a short **"Generate SDK documentation"** section after the existing "Build an
SDK and CLI" block:
- 1–2 sentence pitch: generated SDKs can ship their own docs site (CRUD/auth/
  pagination guides + an auto-generated API reference).
- Minimal `docs:` snippet (`docs:\n  showcase_resource: <resource>`).
- The workflow: `phantasos sdk build <product>` emits the docs scaffold; build the
  SDK's site with `uv run nox -s docs` from inside the generated SDK.
- Link to the new authoring `docs:` reference for the full field list.

## File 4: `docs/authoring.md`
Add a new `## docs:` section (placed alongside the other `sdk.yml` block sections,
e.g. after `## facade` / before `## transforms:` — final placement chosen to match
the existing ordering convention). Document every field with the verified
semantics above, note it's **opt-in** (scaffold emitted only when present), show
the minimal example and a fuller example using `operations`/`examples`, and state
the two build entry points (generated SDK's own `nox -s docs`; phantasos's
`sdk-docs` integration session).

---

## Out of scope
- No code changes; no new nox session; no CI changes.
- No `CHANGELOG.md`/version bump (docs-only contribution rules; will record under
  `## [Unreleased]` only if the maintainer wants this treated as a user-facing
  change — confirm at PR time).
- No Mermaid diagram.

## Done criteria
- `uv run nox -s docs` passes (strict build: no broken links, valid nav, all
  internal cross-links resolve — homepage→authoring `docs:`, dev page internal
  anchors).
- All four files updated; new page appears last in the published nav.
