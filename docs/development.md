# Development

This page is for people contributing to **phantasos itself** (not for consumers of
a generated SDK). The guiding rule is simple: the checks you run locally are the
same ones CI runs — both go through [nox](#getting-started-with-nox), so a green
local run means a green pipeline.

## Git branching

phantasos uses two long-lived branches:

- **`develop`** — the integration branch. All everyday work lands here first.
- **`main`** — released code. It is protected and is the only branch that
  publishes.

### The everyday contributor flow

1. Branch off `develop`, naming the branch `feature/<short-slug>` for new work or
   `bugfix/<short-slug>` for a fix.
2. Make your change. Record anything user-facing under the `## [Unreleased]`
   heading in `CHANGELOG.md`.
3. Open a pull request **targeting `develop`** — the default base is `main`, so set
   it explicitly:

   ```bash
   gh pr create --base develop
   ```

4. The PR is **squash-merged** into `develop` once it's approved and green.

Don't bump the version in a feature or bugfix PR — version bumps are part of
cutting a release.

!!! note "Releases and hotfixes are maintainer-only"
    Cutting a release (the version bump and the `develop → main` merge that
    auto-publishes to PyPI) and shipping an urgent hotfix to released code follow a
    separate, carefully ordered procedure. See `CLAUDE.md` in the repo root for the
    full release and hotfix workflow.

## Test setup

Tests live under `tests/`. [pytest](https://docs.pytest.org/) is the runner.

### Running tests

```bash
uv run nox -s tests   # full run: all supported Pythons, with coverage
uv run nox -s gate    # fast offline loop: ruff + mypy + pytest, no coverage
uv run pytest         # ad-hoc: a single file or a -k subset, in the dev env
```

- The `tests` session runs the suite on **Python 3.11–3.14** and enforces a
  minimum coverage threshold (`fail_under`).
- The `gate` session is the fast inner loop — it skips the coverage and
  multi-Python matrix and is what runs automatically after each agent turn.

### Test tiers

Tests range from fast and isolated to full end-to-end, smallest first:

1. **Offline unit / behavioral suite** — the bulk of `tests/`; runs in `gate` and
   `tests`. No network, no Java.
2. **`cli-smoke`** — generates a CLI, installs it into a *clean* virtualenv (its
   declared dependencies only), and runs it. Catches packaging and
   undeclared-dependency regressions the dev-venv tests can't.
3. **`smoke`** — builds the example SDKs end to end. Needs network and Java (both
   auto-provisioned).
4. **`live`** — runs CRUD against a real tenant. Needs `CLIENT_ID` /
   `CLIENT_SECRET` / `SCOPE` in the environment (a local `.env` is read as a
   convenience); it **skips cleanly** when credentials are absent, so running it
   without them is safe.

### Test policy

When writing tests:

- **Prefer real dependencies.** Never mock the system under test.
- **Show evidence before claiming a pass** — run the command and look at its real
  output.
- **Frozen oracles are human-owned.** Some test files are treated as the source of
  truth and must never be weakened just to make work pass. If one looks wrong, stop
  and raise it for review.

!!! note "Automated enforcement"
    These policies are enforced automatically by the agent harness (Stop hooks and
    protected-path globs). The mechanics live in `CLAUDE.md` and
    `.claude/harness.toml`.

## CI/CD pipeline

The pipeline mirrors nox, so there are no surprises between local and CI:

- **On every pull request** — `ci.yml` runs the same sessions you run locally:
  lint, type-check, the test matrix, a strict docs build, and the CLI and build
  smokes.
- **On merge to `main`** — the docs site deploys to GitHub Pages, and if the
  `version` in `pyproject.toml` is new, the package auto-publishes to PyPI with a
  matching GitHub Release.
- **Continuously and weekly** — security scans run: CodeQL, dependency CVE
  auditing, and secret scanning.

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | push to `main`/`develop`, all PRs | Lint, type-check, tests (3.11–3.14), strict docs build, `cli-smoke`, `smoke` |
| `docs.yml` | push to `main` | Builds the docs site and deploys it to GitHub Pages |
| `release.yml` | push to `main` | Detects a new `version` and publishes to PyPI + a GitHub Release |
| `codeql.yml` | push/PR to `main`/`develop`, weekly | CodeQL static security analysis |
| `audit.yml` | push to `main`, PRs, weekly | `pip-audit` dependency vulnerability scan |
| `secrets.yml` | push to `main`, PRs, weekly | Gitleaks secret scanning |

## Getting started with nox

[nox](https://nox.thea.codes/) is the task runner and the single source of truth
for every check. Sessions use [uv](https://docs.astral.sh/uv/) to provision their
environments.

```bash
uv run nox        # run the default gate (lint, type-check, tests, cli-smoke, docs)
uv run nox -l     # list every session with its description
uv run nox -s tests   # run one session by name
```

All sessions:

| Session | What it does | When to run |
|---------|--------------|-------------|
| `lint` | ruff check + format check | Before pushing; part of the default run |
| `type_check` | mypy (strict) | Before pushing; part of the default run |
| `tests` | Full pytest suite with coverage, on Python 3.11–3.14 | Before pushing; part of the default run |
| `gate` | Fast offline ruff + mypy + pytest (no coverage, single env) | The fast inner loop while developing |
| `context` | Regenerate (or `--check`) the `.agents/context/` generated blocks | After changing a subsystem documented under `.agents/context/` |
| `cli-smoke` | Generate a CLI, install it into a clean venv, and run it | Part of the default run; when touching CLI generation |
| `docs` | Build the docs site with `mkdocs build --strict` | After editing docs; part of the default run |
| `docs-serve` | Serve the docs locally with live reload | While editing docs |
| `audit` | `pip-audit` dependency CVE scan | Occasionally; **online** (queries advisory databases) |
| `smoke` | Build the example SDKs end to end | When touching the build pipeline; **needs network + Java** (auto-provisioned) |
| `live` | Build the prisma-browser SDK and run its live CRUD suite | At phase boundaries; **needs a real tenant's creds** (skips without), network + Java |
| `sdk-docs` | Build the prisma-browser SDK *and its docs* and run `mkdocs build --strict` | When touching generated-SDK docs; **needs network + Java** (auto-provisioned) |

The default `uv run nox` runs `lint`, `type_check`, `tests`, `cli-smoke`, and
`docs`. The heavier sessions (`smoke`, `live`, `sdk-docs`, `audit`) are opt-in —
run them explicitly with `-s`.
