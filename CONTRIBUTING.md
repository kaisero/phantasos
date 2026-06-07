# Contributing to sdkgen

Thanks for your interest in contributing!

## Development setup

This project uses [uv](https://docs.astral.sh/uv/) for environment management
and [nox](https://nox.thea.codes/) as the task runner.

```bash
git clone https://github.com/kaisero/sdkgen.git
cd sdkgen
uv sync --all-groups
uv run pre-commit install
```

Commit changes to `uv.lock` alongside any dependency changes — it keeps builds
reproducible and drives Dependabot updates.

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

## Releasing

Releases are automated. Tagging a commit `vX.Y.Z` and pushing the tag triggers
the release workflow, which builds and publishes to PyPI via Trusted Publishing.
