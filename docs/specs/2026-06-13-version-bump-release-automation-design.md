# Version-bump-triggered release automation — design

**Status:** approved (grilled 2026-06-13)

## Goal

Replace the manual **tag-triggered** PyPI release with an automatic
**version-bump-triggered** release: when a commit lands on `main` carrying a
`pyproject.toml` version that has not been released yet, the workflow builds the
distributions, publishes them to PyPI (Trusted Publishing), and creates a GitHub
Release whose notes come from the matching `CHANGELOG.md` section. Apply the same
model to the scaffold template so every generated SDK/CLI project inherits it.

## Why (current state)

`/.github/workflows/release.yml` triggers on `push: tags: ["v*"]` and does only
`uv build` → `pypa/gh-action-pypi-publish` (env `pypi`, OIDC). It never creates a
GitHub Release and never reads the CHANGELOG. The scaffold template
`src/phantasos/scaffold/.github/workflows/release.yml.jinja` is byte-identical
(only `{{ distribution }}` is interpolated for the PyPI URL) and is rendered into
**both** generated SDK and CLI projects (the CLI build reuses the same scaffold;
`cli_overrides/` has no release override).

## Hard constraints

- **Keep the workflow filename `release.yml` and `environment: pypi`.** The PyPI
  Trusted Publisher (pending publisher for the first upload) is pinned to the
  workflow filename + environment + repo. Renaming either breaks OIDC auth.
- **PyPI publishes the `pyproject.toml` version, not the tag name** (`uv build`
  reads the static `[project].version`). So the tag is a *marker*, and the
  version source of truth is `pyproject.toml`.
- A tag pushed by the default `GITHUB_TOKEN` does **not** trigger another
  workflow. Hence the **single self-contained workflow** model (no second
  workflow to trigger, no PAT needed).

## Versioning (this release)

Adopt PEP 440 pre-release versioning. Bump phantasos `0.1.0` → **`0.1.0a1`**
(alpha 1) in `pyproject.toml`, and rename the CHANGELOG heading
`## [0.1.0] - 2026-06-13` → `## [0.1.0a1] - 2026-06-13`, updating the link-ref
ladder accordingly (compare `v0.0.1...v0.1.0a1`, tag `v0.1.0a1`). The workflow
matches `## [<pyproject-version>]`, so the two MUST agree.

## Trigger & idempotency

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:        # manual retry valve (safe: gated by the same check)
concurrency:
  group: release
  cancel-in-progress: false # never cancel an in-flight publish
```

The `tags: ["v*"]` trigger is removed (the workflow now creates the tag itself; a
second external tag path would double-fire).

**"Already released?" = the git tag `v<version>` exists.** Tag = source of truth.
Created last (by `gh release create`), so a mid-run failure leaves no tag and a
re-run safely retries. `pypa/gh-action-pypi-publish` runs with
`skip-existing: true` so a retry after a successful upload but failed
tag/release step does not hard-fail on the duplicate.

## Job DAG (least-privilege)

1. **`check`** (`contents: read`) — checkout; read `version` via
   `python -c "import tomllib,…"`; resolve whether `v<version>` already exists
   (e.g. `git ls-remote --tags`); compute `prerelease` (PEP 440 suffix
   `a`/`b`/`rc`/`dev` ⇒ true). If the tag exists ⇒ `release=false` and the run
   no-ops. Else extract the `## [<version>]` CHANGELOG block (awk, from the
   heading to the next `## `); **if empty ⇒ exit non-zero (fail-fast before any
   publish)**; else upload the notes as an artifact and set `release=true`.
   Outputs: `release`, `version`, `prerelease`.
2. **`build`** (`needs: check`, `if: needs.check.outputs.release == 'true'`) —
   `uv build` → upload `dist/`.
3. **`publish`** (`needs: build`, `environment: pypi`, `id-token: write`) —
   download `dist/` → `pypa/gh-action-pypi-publish` (`attestations: true`,
   `skip-existing: true`).
4. **`release`** (`needs: publish`, `contents: write`) — download `dist/` + notes
   → `gh release create v<version> --title v<version> --notes-file notes.md
   [--prerelease] dist/*`. Creates the tag + Release and attaches sdist + wheel.

The fail-fast CHANGELOG check lives in `check` (before `build`/`publish`), so a
missing notes section never results in a partial publish.

## Generated-project parity

`scaffold/.github/workflows/release.yml.jinja` gets the identical DAG/logic. The
only template interpolation remains `{{ distribution }}` (PyPI URL). The
version-read, tag check, CHANGELOG extraction, and `gh release create` steps are
generic — they read the *generated* project's own `pyproject.toml` and
`CHANGELOG.md` at run time, so no extra Jinja parameters are needed. The scaffold
`CHANGELOG.md.jinja` already uses `## [<version>]` headings, so extraction matches.

## Error handling

- Missing/empty CHANGELOG section for a new version → `check` fails red, nothing
  published.
- PyPI upload of an already-present version → `skip-existing` makes it a no-op.
- Partial run (publish ok, release step failed) → no tag created → re-run/dispatch
  retries; publish is a skip-existing no-op, then tag+release complete.
- Unchanged version across pushes → `check` sees the tag, run no-ops (cheap).

## Assumptions / prerequisites (operator-owned, flagged not implemented here)

- Branch protection on `main` requires the CI status checks and disallows
  unreviewed direct pushes (so `main` is green before a version-bump merge; the
  release workflow does not re-run the test matrix — Q5).
- The `pypi` GitHub environment exists; its protection rules decide whether
  `publish` pauses for manual approval (semi- vs fully-automatic).
- The PyPI pending Trusted Publisher is configured for `release.yml` + env
  `pypi` (confirmed). First upload of `phantasos` creates the project.

## Delivery & e2e test

All changes on branch `release-automation` → PR to `main`. The PR runs CI only
(release.yml triggers on push-to-main, not on PRs — no premature publish).
**Merging the PR is the end-to-end test:** the push-to-main event runs the *new*
`release.yml`, which sees `0.1.0a1` as unreleased and publishes it (PyPI
pre-release + GitHub pre-release with the CHANGELOG `[0.1.0a1]` notes, sdist+wheel
attached).

## Out of scope

- Conventional-commits / release-please style automatic version *bumping* (the
  human still bumps `pyproject` + CHANGELOG in a PR).
- TestPyPI dry-run path.
- Re-running the test matrix inside the release workflow.
- A shared/tested Python helper for notes extraction (chose inline — Q8).

## Plan / review

After the spec: `writing-plans` → implementation plan, then an adversarial review
by a CI/CD-expert subagent (GitHub Actions + Python packaging) before execution.
