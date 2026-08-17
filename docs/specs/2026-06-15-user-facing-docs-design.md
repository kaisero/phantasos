# User-facing mkdocs documentation (Set 1) — Design

**Date:** 2026-06-15
**Status:** Design grilled with user. Ready for the implementation plan.
**Scope:** The user-facing documentation published to the mkdocs site — **Set 1**, the follow-up explicitly deferred by the agent-facing context-docs work (Set 2, `2026-06-14-agents-context-docs-design.md`). This set owns the user-facing replacement for the removed `docs/ARCHITECTURE.md`.

## Motivation

The published site (`mkdocs.yml` nav) is three thin/mismatched pages: a sparse Home (install + two commands), a detailed `AUTHORING_A_SPEC.md`, and an auto-generated mkdocstrings API reference. There is **no architecture overview or intent page** on the site — the old `docs/ARCHITECTURE.md` was removed during Set 2 and nothing user-facing replaced it. There are **no diagrams**. And the on-site authoring content overlaps an unlinked `docs/ONBOARDING.md` that will drift.

The goal is a small, clean, maintainer-oriented site: state phantasos's **intent**, give an **architecture overview** with **clean diagrams**, and provide a lean but complete **authoring** path and a terse **CLI reference**. Ethos: *simple, no fluff* — where "no fluff" means cut narrative/over-explanation, **not** cut the field tables a maintainer needs to actually author a product.

The deep, internal mechanism lives in `.agents/context/` (Set 2, agent-facing, loaded on demand). The published docs do **not** duplicate or link into that set — the site is self-contained.

## Decisions (user-confirmed, grilled)

| # | Topic | Decision |
|---|---|---|
| 1 | Primary reader | **SDK/CLI generators (maintainers)** — people who run phantasos to produce SDKs/CLIs. Optimize for their job-to-be-done: understand the system, author a product, run builds. |
| 2 | Hands-on depth | **Quickstart + one consolidated guide** (not a multi-page tutorial series). |
| 3 | Conceptual organization | **One `Architecture` page** carrying intent + overview + both diagrams. |
| 4 | Reference slot | **CLI command reference** replaces the mkdocstrings API reference (maintainers drive phantasos through its CLI, not by importing the package). |
| 5 | Guide depth / "no fluff" | **Lean reference, cut narrative.** Keep ALL actionable field tables (sdk.yml, components, transforms, project, overrides) + examples. Cut the internal-mechanism prose ("how the pipeline works") — that lives in `.agents/context/`. Quickstart on top, then a complete-but-terse config reference. |
| 6 | Diagrams | **Both** Diagram A (three-layer model) **and** Diagram B (build pipeline), each kept clean/minimal. **Mermaid** (renders natively in mkdocs-material; version-controlled; no binary assets). |
| 7 | Intent / scope framing | **Generic headline, PAN context inline.** Lead with the generic "native SDKs/CLIs from OpenAPI specs" capability; add a short **Scope** note that the *maintained* target is Palo Alto Networks products (mirrors `goals-non-goals.md` without changing the existing broad tagline). |
| 8 | Home page | **Landing + minimal first-build.** Headline/tagline, one-paragraph intent, install, the two-command happy path inline, and signpost links to the three other pages. |
| 9 | API-ref machinery | **Remove it all.** Delete `docs/reference.md`, drop the `mkdocstrings` plugin block from `mkdocs.yml`, and remove the `mkdocstrings[python]` docs dependency from `pyproject.toml` (then `uv lock`). |
| 10 | ONBOARDING.md | **Delete after merging.** Fold its unique content (the `products/<name>/` dir-tree visual, step ordering) into the Authoring quickstart, then delete the file. |
| 11 | Authoring filename | **Rename** `AUTHORING_A_SPEC.md` → `authoring.md` (clean `/authoring/` URL). Fix inbound links (`index.md`, repo `README`, `docs/TODO.md`). |
| 12 | CLI reference depth | **Commands + flags only** (terse): `sdk build` `[--no-smoke]`, `cli discover` `[--write-stub]`, `cli build`. No exit-code table, no internals. |

## The doc set (per-page content contract)

Final nav: **Home → Architecture → Authoring a product → CLI reference**.

```
docs/
  index.md          # Home — REWRITE (landing + minimal first-build)
  architecture.md   # NEW — intent + overview + Diagram A + Diagram B
  authoring.md      # RENAMED from AUTHORING_A_SPEC.md — quickstart + lean reference
  cli-reference.md  # NEW — the 3 host commands + flags (terse)
  reference.md      # DELETE (API ref removed)
  ONBOARDING.md     # DELETE (merged into authoring.md)
  TODO.md           # untouched (already excluded from build)
  images/           # untouched (logo)
```

### `index.md` — Home (rewrite)
- H1 + tagline (keep the generic "native, self-contained Python SDKs and CLIs from OpenAPI specs" framing).
- One-paragraph intent (what phantasos is / what it produces).
- **Install** (`pip install -e .`).
- **Minimal first-build** — the two-command happy path (`phantasos sdk build <product>` / `phantasos cli build <product>`) inline so a visitor sees it work immediately.
- Signpost links to Architecture, Authoring a product, CLI reference.

### `architecture.md` — Architecture (new)
- **Intent** — generic capability headline, then a short **Scope** note (maintained target = PAN products; the spec-agnostic implementation is a convenience, not a promise — mirror `goals-non-goals.md`).
- **Architecture overview** — the three-layer mental model + the two-stage `spec → SDK → CLI` flow, in prose, right-altitude (no internal call chains).
- **Diagram A — three layers:** framework code (`src/phantasos/`, version-controlled) · product config (`products/<name>/`, version-controlled, the only customization surface besides the scaffold) · generated artifact (the emitted SDK/CLI project, disposable / regenerated wholesale). Answers *"what are the pieces and which do I edit?"*
- **Diagram B — build pipeline:** `products/<name>/` → `phantasos sdk build` (preprocess → OpenAPI Generator → patch → vendor → scaffold → smoke) → SDK → `phantasos cli build` (introspect → classify → render) → CLI. Answers *"what happens when I run the commands?"* Kept minimal — stage names only, no sub-detail.
- Source of truth for both: `.agents/context/index.md` + `goals-non-goals.md` (distilled, simplified — do not deep-link to them from the site).

### `authoring.md` — Authoring a product (renamed + restructured)
- **Quickstart on top** (new section): create `products/<name>/` (with the dir-tree visual merged from ONBOARDING.md), a minimal `sdk.yml` (required fields + a common component or two), build, done.
- **Config reference** (the existing `AUTHORING_A_SPEC.md` tables, kept complete): `sdk.yml` fields, `generator:`, components (`auth`/`pagination`/`errors`/`facade` + custom templates), `transforms:`, `hooks:`, `vars:`, `include:`, `project:`, `overrides/`, concrete examples.
- **Cut:** the internal-mechanism narrative (e.g. the "build pipeline" prose paragraph that restates Diagram B) — replace with a one-line pointer to the Architecture page. Keep all field semantics.

### `cli-reference.md` — CLI reference (new)
- Terse: each host command with a one-line purpose and its flags.
  - `phantasos sdk build <product>` `[--no-smoke]`
  - `phantasos cli discover <product>` `[--write-stub]`
  - `phantasos cli build <product>`
- One line that a product is given as a name (resolved to `products/<name>/sdk.yml`) **or** a direct path to an `sdk.yml`.
- No exit-code table, no internals (those live in `.agents/context/phantasos-cli.md`).

## Mechanical changes (outside `docs/`)

- **`mkdocs.yml`:** rewrite `nav` to the four pages; **remove** the `mkdocstrings` plugin block (keep `search`); add the Mermaid custom-fence to `pymdownx.superfences` so ` ```mermaid ` blocks render:
  ```yaml
  markdown_extensions:
    - pymdownx.superfences:
        custom_fences:
          - name: mermaid
            class: mermaid
            format: !!python/name:pymdownx.superfences.fence_code_format
  ```
  (mkdocs-material ships mermaid.js — no new dependency.)
- **`pyproject.toml`:** `docs = ["mkdocs-material>=9.5", "mkdocstrings[python]>=0.25"]` → `docs = ["mkdocs-material>=9.5"]`; then `uv lock`.
- **Source error messages** (delete-ONBOARDING fallout — verified there are no tests asserting these strings, and the files are not protected oracles):
  - `src/phantasos/cli.py:125` — `see docs/ONBOARDING.md` → `see docs/authoring.md`
  - `src/phantasos/generator/sdk/build.py:82` — `see docs/ONBOARDING.md` → `see docs/authoring.md`
  - `src/phantasos/generator/sdk/build.py:88` — `see docs/ONBOARDING.md` → `see docs/authoring.md`
- **Inbound doc links:** `docs/TODO.md:111` (`docs/AUTHORING_A_SPEC.md` → `docs/authoring.md`); repo `README` if it links the old name; `index.md` is rewritten anyway.

## Branching note (to confirm in the plan)

The Set 2 work (`.agents/context/`, tip `c6be904`) is **not yet merged** to `develop`. Set 1's published docs are self-contained (no dependency on `.agents/context/` files in the tree), so this work can branch cleanly off `develop` as `feature/user-facing-docs` and PR into `develop` (squash) — independent of Set 2's merge. The plan opens by confirming the branch base. Per `CLAUDE.md`: target `--base develop`, record under `## [Unreleased]`, **no version bump**.

## Validation

- **Build:** `uv run mkdocs build --strict` succeeds (no broken nav/links, no missing-file warnings) after the changes.
- **Diagrams:** both Mermaid blocks render (verify in `mkdocs serve` / built `site/`), not shown as raw code fences.
- **No dead pointers:** grep confirms zero remaining references to `ONBOARDING.md`, `AUTHORING_A_SPEC.md`, `reference.md`, or `mkdocstrings` outside `docs/specs/` and `docs/plans/`.
- **Offline gate:** `uv run nox -s gate` passes (the source error-string edits don't break tests).
- **Lock integrity:** `uv lock` clean after the dependency removal.

## Out of scope

- The `.agents/context/` agent-facing set (Set 2 — done/separate).
- Changing the site theme, hosting, or the GitHub Pages deploy workflow.
- Reintroducing API reference / mkdocstrings in any form.
- Documenting any specific generated SDK/CLI's surface (per-product, dynamic).
- Any version bump or release act (feature work → `## [Unreleased]` only).
