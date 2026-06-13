# Contributing to phantasos

Thanks for your interest in contributing!

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for environment management
and [nox](https://nox.thea.codes/) as the task runner.

```bash
git clone https://github.com/kaisero/phantasos.git
cd phantasos
uv sync --all-groups
uv run pre-commit install
```

Commit changes to `uv.lock` alongside any dependency changes — it keeps builds
reproducible and drives Dependabot updates.

## Branching

- **`main`** holds released code and is protected — it publishes to PyPI on every
  release, so don't target it for routine work.
- **`develop`** is the integration branch. Branch your work from `develop` and
  open PRs **back into `develop`** (set the PR base to `develop` — `main` is the
  repo default, so double-check the base):
  - `feature/<short-name>` — new functionality
  - `bugfix/<short-name>` — non-urgent fixes
- Add a `CHANGELOG.md` entry under `## [Unreleased]`, and **do not bump the
  version** in a feature/bugfix PR (versioning happens only at release time).
- `hotfix/<short-name>` (branched off `main`) is reserved for urgent fixes to an
  already-released version; maintainers own the patch release and the back-merge.

## Before opening a pull request

Run the full suite of checks — the same ones CI runs:

```bash
uv run nox
```

Or individually:

| Check        | Command                  |
| ------------ | ------------------------ |
| Lint/format  | `uv run nox -s lint`      |
| Type-check   | `uv run nox -s type_check` |
| Tests        | `uv run nox -s tests`     |
| Docs         | `uv run nox -s docs`      |
| Audit (CVEs) | `uv run nox -s audit`     |

Please:

- Add tests for new behavior (coverage gate is 70%).
- Keep public APIs typed and documented (Google-style docstrings).
- Add an entry under `## [Unreleased]` in `CHANGELOG.md`.

## Releasing (maintainers)

Releases are automated and **version-driven** — a version bump landing on `main`
publishes. To cut release `X.Y.Z`:

1. On `develop`, make a `release: X.Y.Z` commit: set `version = "X.Y.Z"` in
   `pyproject.toml`, move the `## [Unreleased]` notes into a new
   `## [X.Y.Z] - <date>` section (leave a fresh empty `## [Unreleased]` above) and
   update the link-ref ladder, then run `uv lock`.
2. Open a `develop → main` PR and **merge it with a merge commit** (not squash —
   that would diverge `develop` from `main`).

Merging the bump to `main` triggers the `Release` workflow, which builds the sdist
+ wheel, publishes to PyPI via Trusted Publishing, and creates a GitHub Release
`vX.Y.Z` with the matching `CHANGELOG.md` section. PEP 440 pre-releases
(e.g. `0.2.0a1`) publish as pre-releases. The workflow is idempotent: if
`vX.Y.Z` is already released it no-ops, and it fails fast if the `## [X.Y.Z]`
CHANGELOG section is missing.
