# release-workflow

Validated against 2bcfa34 on 2026-06-14 · Purpose: mechanism and rationale of the branching model and release automation — the system that turns a version bump on `main` into a published PyPI package and GitHub Release.

The **binding rules** (two long-lived branches, merge strategies, cutting a release, hotfix, back-merge) live in `CLAUDE.md` "Branching & release workflow". This document explains how the mechanism works and why it is designed the way it is. Do not look here for the rules.

---

## The two branches

`main` is the only branch that ever publishes. It is protected, the GitHub default, and holds only released code. `develop` is the integration branch — it never triggers a publish, and direct pushes are reserved for trivial non-code changes (typos, comments). Feature and bugfix work lives on short-lived branches that merge back into `develop` by squash; `develop` merges into `main` by merge commit at release time. The full rules — including hotfix branching, back-merge procedure, and merge-strategy enforcement — are in `CLAUDE.md`.

---

## How release.yml works

`.github/workflows/release.yml` fires on any push to `main` (and via `workflow_dispatch` for manual retries). Its four jobs form a dependency chain:

**`check` — detect unreleased version.** Reads `version` from `pyproject.toml` via `tomllib`, asserts it is PEP 440-canonical, and determines whether `v<version>` already exists as a GitHub Release tag (`gh release view`). If the tag exists the run no-ops immediately — unchanged-version pushes are cheap. If the version is new, it extracts the `## [<version>]` block from `CHANGELOG.md` using `awk` (from the heading to the next `## [` line). An empty or missing section fails the job red before any build or publish step runs. It also classifies the version as a pre-release (any PEP 440 pre-release suffix: `a`, `b`, `rc`, `dev`) and surfaces `release`, `version`, and `prerelease` as job outputs.

**`build` — produce sdist and wheel.** Runs `uv build`, uploads `dist/` as an artifact. Skipped entirely if `check` output `release=false`.

**`publish` — PyPI via Trusted Publishing.** Downloads `dist/`, publishes with `pypa/gh-action-pypi-publish` (OIDC, PEP 740 attestations, `skip-existing: true`). Runs under the `pypi` environment with `id-token: write`; `contents` is kept at `read`. `skip-existing` makes the step idempotent — a retry after a successful upload but a failed downstream step does not hard-fail on the duplicate.

**`release` — create GitHub Release and tag.** Downloads `dist/` and the `notes.md` artifact from `check`, then calls `gh release create v<version> --title v<version> --notes-file notes.md [--prerelease] dist/*`. This step creates the tag. Because the tag is created last, a partial run (publish ok, release step failed) leaves no tag, and a re-run retries cleanly.

PEP 440 pre-releases (e.g. `0.1.0a1`) pass `--prerelease` to `gh release create` and publish to PyPI as pre-releases. The workflow detects them automatically from the version string — no manual flag needed.

---

## Why this design

**Version-driven, not tag-driven.** The previous `release.yml` triggered on `push: tags: ["v*"]`. That required a separate manual step to push a tag, and the workflow never created a GitHub Release or read the CHANGELOG. The version-bump-triggered design collapses those into a single act: bump `pyproject.toml` and merge to `main`. The design spec (`docs/specs/2026-06-13-version-bump-release-automation-design.md`) records the full rationale. One important constraint: a tag pushed by the default `GITHUB_TOKEN` does not re-trigger another workflow, so the workflow must be self-contained (no second workflow needed, no PAT needed).

**`pyproject.toml` is the version source of truth.** `uv build` reads `[project].version` from `pyproject.toml` to populate the wheel metadata. The CHANGELOG section heading `## [<version>]` must match exactly. The `test_config_packaged_defaults_match_models` test (offline gate) catches config drift; the release workflow's `check` job catches CHANGELOG drift.

**Squash into `develop`, merge commit into `main`.** Squash keeps `develop` history tidy — a feature is one logical commit. But `develop → main` must be a merge commit so that `develop` and `main` share a common ancestor at every release point. If `develop` were squashed or rebased onto `main`, the next release's PR would have no useful merge-base, and history would diverge. The merge commit means `develop` showing "behind `main` by one commit" after a release is cosmetic — that one commit is the merge commit itself, and the next release PR will merge cleanly.

**`develop` never publishes.** The `release.yml` trigger is `branches: [main]` only. Merging anything to `develop` — including a version bump — never fires the publish workflow. This prevents accidental publishes during integration work.

**Idempotency throughout.** The `check` job's tag-existence test makes every subsequent push of the same version a cheap no-op. `skip-existing: true` in the publish step absorbs retries. The tag is created last so failure leaves the run in a state that a re-run can recover.

---

## Build / run pointers

- Release workflow: `.github/workflows/release.yml`
- CI workflow (lint + type-check + 4-version test matrix + docs + smoke): `.github/workflows/ci.yml` — runs on PRs and on pushes to `main`/`develop`
- Cutting a release (version bump + CHANGELOG rename + `uv lock` + `develop → main` PR): see `CLAUDE.md` "Cutting a release"
- PRs must be opened with `gh pr create --base develop` for feature/bugfix branches (the GitHub default base is `main` — see `CLAUDE.md`)

---

## Gotchas

**Any merge method that lands a changed `version` on `main` auto-publishes.** It does not matter whether the merge was a squash, a merge commit, or a direct push. The `check` job sees the version in `pyproject.toml` and acts. The workflow `concurrency.cancel-in-progress: false` ensures an in-flight publish is never cancelled by a racing push.

**Missing CHANGELOG section fails before any publish.** If `## [<version>]` is absent or empty in `CHANGELOG.md`, the `check` job exits non-zero and neither `build` nor `publish` runs. This is intentional: a partial publish (PyPI succeeds, GitHub Release has no notes) is worse than a hard stop.

**"Develop is behind main by the release merge commit" is cosmetic.** After a `develop → main` merge, `develop` appears behind by one commit (the merge commit). This is expected and correct — do not back-merge `main` into `develop` to "fix" it. The next release PR will merge cleanly. Back-merging is only needed after a hotfix (see `CLAUDE.md`).

**Hotfix back-merge collision resolution.** A hotfix branches from `main`, bumps the patch version, and merges back to `main`. Back-merging `main` into `develop` then produces version/CHANGELOG conflicts. Resolution is deterministic: take `main`'s version and its new `## [X.Y.Z]` section, keep `develop`'s `## [Unreleased]` contents, and ensure exactly one `## [Unreleased]` header and one `[Unreleased]:` link-ref survive. See `CLAUDE.md` "Back-merging a hotfix".

**CHANGELOG link-ref ladder must be kept current.** The `[Unreleased]:` link-ref compares against the latest released tag. After a release, rename it to compare against `v<new-version>`. A stale ladder does not break the publish, but it produces incorrect diff links on GitHub.

---

## See also

- `CLAUDE.md` — the binding rules (branching, merge strategies, cutting a release, hotfix, back-merge).
- `docs/specs/2026-06-13-version-bump-release-automation-design.md` — the full design: rationale for version-driven vs tag-driven, job DAG, error-handling, idempotency constraints, and delivery plan.
- `.agents/context/harness-and-testing.md` — the quality harness that gates every agent stop and enforces test integrity before anything reaches `develop` or `main`.
- `.agents/context/index.md` — system overview and links to all deep-dives.
