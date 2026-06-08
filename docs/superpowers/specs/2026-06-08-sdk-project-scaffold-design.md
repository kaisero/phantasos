# Design: SDK project scaffolding (Phase C)

**Date:** 2026-06-08
**Status:** Draft for review
**Branch:** `sdk-project-scaffold` (stacked on `declarative-products-config` → `isolated-smoke-venv` → `main`)

## Goal

Make every generated SDK a **phantasos-grade project**: replace OpenAPI Generator's
scaffolding (setup.py, tox.ini, requirements.txt, git_push.sh, travis/gitlab CI, OAG README)
with a curated, value-substituted project — `pyproject.toml`, robust CI/CD (lint, type-check,
test matrix, PyPI release, audit, secrets, codeql, docs), pre-commit, and a behavioral test
suite — all driven from version-controlled templates so they survive regeneration.

## Why this is safe to do (the "deleted tests" finding)

Empirically verified: `phantasos build` / OpenAPI Generator is **non-destructive** to custom
files in the output dir (sentinel files survived a real regeneration; OAG only rewrites files
in its own `.openapi-generator/FILES` manifest). The earlier loss of `prisma-browser-sdk/tests/`
was **not** caused by the build — those tests simply lived in a non-version-controlled,
regenerated directory. **This design fixes that structurally:** all SDK content (tests, CI,
config) is generated each build from templates under phantasos's version control, so it can
never be lost.

## Model: built-in scaffold + per-product overrides (overwrite every build)

- **Built-in scaffold** `src/phantasos/scaffold/`: Jinja templates mirroring the SDK project
  tree — the single source of truth for "robust SDK project config." Fix a CI bug once here,
  every SDK inherits it on rebuild.
- **Per-product overrides** `products/<product>/overrides/`: same tree; a file at the same
  relative path **replaces** the built-in one; everything else falls through to the built-in.
- **Overwrite-everything:** the SDK is a pure build artifact. You never hand-edit it; all
  customization lives in phantasos's `products/` + `scaffold/` + `sdk.yml`, under git.

### Scaffold tree (built-in: `src/phantasos/scaffold/`)

```
pyproject.toml.jinja                 # SDK packaging + tool config; DEFAULT runtime deps
noxfile.py.jinja                     # lint/type-check/test sessions
.pre-commit-config.yaml.jinja
.github/workflows/ci.yml.jinja       # lint + mypy + pytest matrix
.github/workflows/release.yml.jinja  # PyPI trusted publishing
.github/workflows/audit.yml.jinja    # pip-audit
.github/workflows/secrets.yml.jinja  # gitleaks
.github/workflows/codeql.yml.jinja
.github/workflows/docs.yml.jinja
mkdocs.yml.jinja
.gitignore.jinja  .editorconfig  LICENSE.jinja
CHANGELOG.md.jinja  CONTRIBUTING.md.jinja  SECURITY.md.jinja
tests/                               # built-in COMPONENT-behavior tests (see below)
  conftest.py.jinja
  test_auth.py.jinja                 # rendered only if has_auth
  test_pagination.py.jinja           # rendered only if has_pagination
  test_errors.py.jinja               # rendered only if has_errors
  test_facade.py.jinja               # rendered only if has_facade
  test_lenient_enums.py.jinja        # rendered if patches/lenient enums apply
```

### Per-product overrides (`products/<product>/overrides/`)

```
README.md.jinja                      # REQUIRED — README is always per-product
tests/                               # OPTIONAL — model/integration tests for this API
  test_models.py.jinja
```

(README is intentionally NOT in the built-in scaffold — each SDK gets its own.)

## Tests: built-in component tests + per-product model tests

The lost suite had two kinds; they get different homes:

- **Component-behavior tests** (auth, pagination, errors, facade, lenient-enums) test
  phantasos's **own vendored components** — generic to any SDK that vendors them. They ship
  in the **built-in scaffold**, rendered with the package name and **gated on
  `has_auth`/`has_pagination`/`has_errors`/`has_facade`**. Every SDK that vendors a component
  automatically gets its behavioral test. (These reconstruct the lost prisma-browser tests,
  generalized — and version-controlled, so never lost again.)
- **Model/spec-specific tests** (e.g. `User.from_dict` round-trip) are per-product in
  `overrides/tests/`.

Both render into the SDK's `tests/` and run under the scaffold's CI. `conftest.py` puts the
package on `sys.path` (the SDK isn't installed editable during its own CI by default —
mirror the existing prisma-browser-sdk `conftest` pattern).

## New `sdk.yml` section: typed `project:` block

```yaml
project:
  distribution: prisma-browser-sdk          # PyPI name (distinct from import `package`)
  description: Python SDK for the Prisma Browser Management APIs
  author: Oliver Kaiser
  author_email: oliver.kaiser@outlook.com
  repo_url: https://github.com/kaisero/prisma-browser-sdk
  license: Apache-2.0                        # default
  python_versions: ["3.11", "3.12", "3.13", "3.14"]   # default = phantasos matrix
  dependencies:                              # OPTIONAL override of the base deps
    - "urllib3 >= 2.1.0, < 3.0.0"
    - "python-dateutil >= 2.8.2"
    - "pydantic >= 2.11"
    - "typing-extensions >= 4.7.1"
```

Pydantic-validated (`extra="forbid"`); `distribution`/`author`/`repo_url` required; `license`
defaults `Apache-2.0`; `python_versions` defaults to phantasos's matrix; `dependencies`
defaults to the **base deps** below. All `project.*` fields are auto-exposed to scaffold
templates (e.g. `{{ project.repo_url }}` or flattened `{{ repo_url }}` — flattened, consistent
with existing auto-exposure).

### Base runtime deps (scaffold default)

Verified identical across `prisma-browser-sdk` and `adem-sdk`, so they are the default for all
SDKs (overridable via `project.dependencies`):

```
urllib3 >= 2.1.0, < 3.0.0
python-dateutil >= 2.8.2
pydantic >= 2.11
typing-extensions >= 4.7.1
```

## Suppressing OAG's scaffolding (`.openapi-generator-ignore`)

Before generation, phantasos writes a curated `.openapi-generator-ignore` into the output dir
listing the OAG supporting files we replace, so OAG never writes them:

```
setup.py
setup.cfg
requirements.txt
test-requirements.txt
tox.ini
git_push.sh
.gitlab-ci.yml
.travis.yml
.github/workflows/python.yml
README.md
```

(We keep OAG's `.openapi-generator/` metadata and the generated package itself.)

## Smoke change

Because OAG's `requirements.txt` is suppressed, the isolated smoke check switches from
`pip install -r requirements.txt` to **`pip install <project_dir>`** (installs the SDK + its
declared deps from the scaffolded `pyproject.toml`). `_ensure_smoke_venv` is updated
accordingly (cache key becomes a hash of the resolved deps / pyproject).

## Build pipeline (updated)

```
load+validate sdk.yml
  -> write .openapi-generator-ignore (suppress OAG scaffolding)
  -> preprocess (transforms -> hooks)
  -> generate (OAG; emits package, no suppressed files)
  -> patch (generic -> hooks)
  -> vendor (components + include -> <package>/extras/)
  -> SCAFFOLD: render built-in scaffold + per-product overrides -> SDK root (overwrite)
  -> provenance (_about.py)
  -> smoke (pip install <project_dir> + import-walk)
```

A new `scaffold.py` module owns the scaffold step: walk the built-in `scaffold/` tree and the
product's `overrides/` tree, apply same-path-override, render each `.jinja` with the unified
context (now including `project.*`), strip `.jinja`, write to the SDK at the mirrored path.
Non-`.jinja` files (e.g. `.editorconfig`) are copied verbatim.

## Onboarding a new SDK (documented for Claude/authors)

`docs/ONBOARDING.md` (new) describes the flow:
1. Create `products/<name>/{openapi.yml, sdk.yml}` (+ `overrides/README.md.jinja`).
2. Run `phantasos build <name>` once. The scaffold's **default deps** are usually correct
   (all `library=urllib3` SDKs share them).
3. If the SDK needs different deps (rare), generate once *without* suppression to read OAG's
   `requirements.txt`, then set `project.dependencies` in `sdk.yml`. A one-off smoke failure
   from a missing dep is an acceptable signal, not a blocker.

## Migration of the two example products

- Add a `project:` block to `products/{adem,prisma-browser}/sdk.yml`.
- Add `products/<product>/overrides/README.md.jinja` for each.
- Add `products/prisma-browser/overrides/tests/test_models.py.jinja` (the `User` round-trip
  test, reconstructed/generalized from the lost suite) — adem may have none.
- Rebuild both; confirm the SDK now has pyproject (no setup.py/requirements.txt/tox.ini),
  the CI/release/etc. workflows, the rendered component tests, and that smoke (pip install)
  passes.

## Out of scope

- Actually publishing the SDKs to PyPI / running their CI in the cloud (the workflows are
  scaffolded but not triggered here).
- Per-SDK docs hosting setup beyond emitting `mkdocs.yml` + `docs.yml`.
- Any change to the generated *package* code or the components (Phase A+B covered those).

## Risks / notes

- **Branch stack depth:** this is the 3rd unmerged branch on top of `main`. Recommend
  collapsing the stack (merge isolated-smoke + declarative to main) before or soon after
  this phase to avoid a deep rebase chain.
- **Template volume:** ~14 scaffold templates + component tests is the bulk of the work; each
  is phantasos's own infra file adapted to a generic SDK with `{{ project.* }}` substitution.
- **Scaffold drift vs phantasos's own infra:** the SDK scaffold is *similar to* but not a copy
  of phantasos's infra (SDK is a library, not a generator). Keep them separate; don't try to
  share one template set.
