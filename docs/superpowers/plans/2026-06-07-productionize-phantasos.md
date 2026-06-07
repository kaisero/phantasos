# Productionize phantasos (merge python-project-template) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the `phantasos` repo up to a production-grade Python setup by merging the `~/git/python-project-template` (Copier) template into it — gaining uv/nox/ruff/mypy/pytest, MkDocs docs, and full GitHub Actions CI/CD — without breaking the working phantasos generator or its two example specs.

**Architecture:** Apply the Copier template *into* the existing repo (writing `.copier-answers.yml` so future `copier update` works), then reconcile conflicts file-by-file: template wins for new tooling/scaffolding, our code wins for the engine, and `pyproject.toml`/`.gitignore`/`ci.yml`/docs-nav are hand-merged. Migrate the package to a `src/phantasos/` layout. All work happens on a new branch and lands as **one squashed commit**.

**Tech stack:** Copier, uv (+ uv.lock, PEP 735 dependency-groups), hatchling, nox, ruff, mypy (strict), pytest + pytest-cov, MkDocs Material + mkdocstrings, GitHub Actions (CI matrix, PyPI Trusted Publishing, Pages, Dependabot, CodeQL), JDK 17 + OpenAPI Generator (for the build-smoke).

**Resolved decisions (from grill-me):**
- Mechanism: **A** — Copier into the repo (lineage via `.copier-answers.yml`); reconcile by hand. One squashed commit on a new branch.
- Layout: migrate `phantasos/` → **`src/phantasos/`**.
- CLI: **keep argparse** (`include_cli=false`); Typer port is a documented follow-up.
- mypy: **strict**, pragmatic per-module overrides only where dynamic code/untyped deps require.
- Coverage: **70%**, integration glue (`generate.py`) excluded — proven by a Java build-smoke instead.
- Build-smoke: dedicated **`nox -s smoke`** session + a JDK17 CI job (jar-cached); builds **both** prisma-browser and adem.
- Docs: full **MkDocs** with curated nav (Home, Authoring, Architecture, API Reference, Project history) + Pages deploy.
- Metadata: project/slug/package all `phantasos`; Apache-2.0; owner `kaisero`; `oliver.kaiser@outlook.com`; Python ≥3.11; copyright 2026.
- Conflicts: template wins for new tooling; ours wins for engine/specs/transformations/our-docs; `pyproject.toml`/`.gitignore`/`ci.yml`/mkdocs-nav merged; README ours + badges.

**Commit policy:** Commit per task on the branch for safety checkpoints; the **final task squashes all task commits into one** so the branch presents a single commit for merging into `main`.

**Baseline to preserve (must still be true at the end):**
- `uv run nox -s smoke` builds prisma-browser → 427 modules, 0 failures, 95 ops; adem → 110 modules, 0 failures, 13 ops.
- `python -m pytest tests/` → 9 passed (engine tests).
- Generated SDKs still land in siblings `../prisma-browser-sdk/`, `../adem-sdk/`; nothing generated inside the repo.

---

## Task 0: Branch + baseline capture

**Files:** none (git only)

- [ ] **Step 1: Confirm clean tree on `main`**

Run: `cd /home/ubuntu/git/pan-phantasoserator && git status --short | grep -v fuse_hidden`
Expected: no output (clean; ignore any `.fuse_hidden*`).

- [ ] **Step 2: Create the work branch**

```bash
git checkout main
git checkout -b chore/productionize-template
```
Expected: `Switched to a new branch 'chore/productionize-template'`

- [ ] **Step 3: Capture the baseline build numbers** (so we can prove parity later)

```bash
uv run --no-project --python 3.12 \
  --with ruamel.yaml --with jinja2 --with pydantic --with urllib3 \
  --with python-dateutil --with typing_extensions \
  python -m phantasos.cli build transformations/prisma-browser.py
```
Expected: `built prisma_browser: imported 427 modules, 0 failures; operations: 95`

```bash
rm -rf ../prisma-browser-sdk/.phantasos ../adem-sdk/.phantasos
```

---

## Task 1: Apply the Copier template into the repo

**Files:** many new (template scaffolding) + `.copier-answers.yml`; overwrites `README.md`, `pyproject.toml`, `.gitignore`, `.github/workflows/ci.yml`.

- [ ] **Step 1: Run Copier non-interactively into the repo**

```bash
uvx copier copy --trust --overwrite --defaults --vcs-ref=HEAD \
  --data project_name=phantasos \
  --data project_slug=phantasos \
  --data package_name=phantasos \
  --data "description=Generate native, self-contained Python SDKs from OpenAPI specs." \
  --data "author_name=Oliver Kaiser" \
  --data author_email=oliver.kaiser@outlook.com \
  --data github_owner=kaisero \
  --data license=Apache-2.0 \
  --data min_python=3.11 \
  --data include_cli=false \
  --data coverage_threshold=70 \
  --data copyright_year=2026 \
  /home/ubuntu/git/python-project-template .
```
Expected: Copier prints generated files and the `_message_after_copy`. A `.copier-answers.yml` now exists.

Note: `--vcs-ref=HEAD` makes Copier render the template's committed HEAD. If the template repo has uncommitted changes you need, commit them in `~/git/python-project-template` first. If Copier refuses the local path, use `--vcs-ref=HEAD` with the path as shown (Copier supports local git templates).

- [ ] **Step 2: Verify the answers file + key new files exist**

Run: `cat .copier-answers.yml; ls noxfile.py mkdocs.yml LICENSE .pre-commit-config.yaml .editorconfig .github/workflows/codeql.yml`
Expected: answers file shows the data above; all listed files exist.

- [ ] **Step 3: Commit the raw template application** (checkpoint)

```bash
git add -A
git commit -m "wip: apply python-project-template via copier (raw)"
```

---

## Task 2: Reconcile "ours wins" files + drop template stubs

**Files:**
- Restore: `README.md` (ours)
- Delete: `src/phantasos/core.py`, `src/phantasos/__init__.py` (template stubs — replaced in Task 3), `tests/test_core.py`, `tests/test_cli.py` (if present)

- [ ] **Step 1: Restore our README (keep template's as a reference for badges in Task 12)**

```bash
git show main:README.md > README.md
```

- [ ] **Step 2: Delete template package + test stubs we don't want**

```bash
git rm -f --ignore-unmatch tests/test_core.py tests/test_cli.py
rm -f src/phantasos/core.py src/phantasos/__init__.py
```
(We keep `src/phantasos/py.typed` from the template. Our real modules move in next task.)

- [ ] **Step 3: Sanity-check what the template added vs. what we keep**

Run: `git status --short`
Expected: deleted `tests/test_core.py`; `README.md` modified back to ours; `src/phantasos/` currently holds only `py.typed`.

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: keep our README; drop template package/test stubs"
```

---

## Task 3: Migrate the package to `src/phantasos/`

**Files:**
- Move: `phantasos/*` → `src/phantasos/*` (incl. `components/**/*.jinja`)
- Modify: `tests/conftest.py`

- [ ] **Step 1: Move the package under `src/` (keep template's `py.typed`)**

```bash
git mv phantasos/__init__.py        src/phantasos/__init__.py
git mv phantasos/cli.py             src/phantasos/cli.py
git mv phantasos/config.py          src/phantasos/config.py
git mv phantasos/generate.py        src/phantasos/generate.py
git mv phantasos/patches.py         src/phantasos/patches.py
git mv phantasos/preprocess.py      src/phantasos/preprocess.py
git mv phantasos/render.py          src/phantasos/render.py
git mv phantasos/smoke.py           src/phantasos/smoke.py
git mv phantasos/components         src/phantasos/components
rmdir phantasos 2>/dev/null || true
```
Expected: `src/phantasos/` now has all modules + `components/` + `py.typed`; `phantasos/` is gone.

- [ ] **Step 2: Point the test conftest at `src/`**

Replace `tests/conftest.py` entirely with:

```python
"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
```

- [ ] **Step 3: Verify the package imports from src/**

Run: `cd /home/ubuntu/git/pan-phantasoserator && PYTHONPATH=src uv run --no-project --python 3.12 --with jinja2 --with ruamel.yaml python -c "import phantasos; print(phantasos.__file__)"`
Expected: a path ending in `src/phantasos/__init__.py`.

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: migrate package to src/phantasos layout"
```

---

## Task 4: Merge `pyproject.toml`

**Files:**
- Modify: `pyproject.toml` (template base + our deps/scripts/package-data + tool overrides)

- [ ] **Step 1: Replace `pyproject.toml` with the merged version**

Write `pyproject.toml` exactly as:

```toml
[project]
name = "phantasos"
version = "0.1.0"
description = "Generate native, self-contained Python SDKs from OpenAPI specs."
readme = "README.md"
requires-python = ">=3.11"
license = "Apache-2.0"
license-files = ["LICENSE"]
authors = [{ name = "Oliver Kaiser", email = "oliver.kaiser@outlook.com" }]
keywords = ["openapi", "sdk", "codegen", "openapi-generator"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
    "Typing :: Typed",
]
dependencies = [
    "ruamel.yaml>=0.18",
    "jinja2>=3.1",
]

[project.urls]
Homepage = "https://github.com/kaisero/phantasos"
Documentation = "https://kaisero.github.io/phantasos/"
Repository = "https://github.com/kaisero/phantasos"
Issues = "https://github.com/kaisero/phantasos/issues"
Changelog = "https://github.com/kaisero/phantasos/blob/main/CHANGELOG.md"

[project.scripts]
phantasos = "phantasos.cli:main"

[project.optional-dependencies]
# Deps the *generated* SDK imports at smoke/runtime — installed so `phantasos build`
# can import-check its own output. A built SDK declares these in its own pyproject.
generated = ["pydantic>=2", "urllib3>=2", "python-dateutil", "typing_extensions"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/phantasos"]
# Ship the Jinja component templates as package data (vendored at build time).
artifacts = ["src/phantasos/components/**/*.jinja"]

[tool.hatch.build.targets.sdist]
include = ["src/phantasos", "README.md"]

[dependency-groups]
test = ["pytest>=8", "pytest-cov>=5"]
typecheck = ["mypy>=1.11", { include-group = "test" }]
lint = ["ruff>=0.6", "codespell>=2.3"]
audit = ["pip-audit>=2.7"]
docs = ["mkdocs-material>=9.5", "mkdocstrings[python]>=0.25"]
# Deps the generated SDK imports, so `nox -s smoke` can import-check its output.
smoke = ["pydantic>=2", "urllib3>=2", "python-dateutil", "typing_extensions"]
dev = [
    "nox>=2024.4",
    "pre-commit>=3.7",
    { include-group = "test" },
    { include-group = "typecheck" },
    { include-group = "lint" },
    { include-group = "audit" },
    { include-group = "docs" },
]

[tool.ruff]
target-version = "py311"
line-length = 88
src = ["src", "tests", "transformations"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "S", "ASYNC", "PTH", "RUF"]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "S107"]
# generate.py runs the pinned OpenAPI Generator jar and fetches it over https — trusted.
"src/phantasos/generate.py" = ["S603", "S404", "S310"]

[tool.ruff.lint.isort]
known-first-party = ["phantasos"]

[tool.ruff.format]
docstring-code-format = true

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
files = ["src", "tests"]

[[tool.mypy.overrides]]
module = ["ruamel", "ruamel.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"

[tool.coverage.run]
branch = true
source = ["phantasos"]
# generate.py is a thin subprocess wrapper around the OpenAPI Generator jar; it is
# exercised by `nox -s smoke` (which needs Java), not the unit suite.
omit = ["src/phantasos/generate.py"]

[tool.coverage.report]
show_missing = true
fail_under = 70
exclude_also = [
    "if TYPE_CHECKING:",
    "\\.\\.\\.",
]

[tool.codespell]
skip = "*.lock,./.git,./.nox,./.venv,./site,./specs,./docs/phase-*.md"
```

- [ ] **Step 2: Verify it parses and resolves**

Run: `uv sync --all-groups`
Expected: resolves, creates `.venv` + `uv.lock`, no errors.

- [ ] **Step 3: Verify the console script + import work from the install**

Run: `uv run phantasos --help`
Expected: argparse help showing the `build` subcommand.

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: merge pyproject (deps, scripts, package-data, tool config)"
```

---

## Task 5: Add the `nox -s smoke` session

**Files:**
- Modify: `noxfile.py` (append a `smoke` session)

- [ ] **Step 1: Append the smoke session to `noxfile.py`**

Add at the end of `noxfile.py`:

```python
@nox.session
def smoke(session: nox.Session) -> None:
    """Build the example SDKs end-to-end (requires JDK 17 + network for the OAG jar).

    Not in the default session list because it needs Java and the OpenAPI Generator
    jar. Each SDK is written to a sibling dir of this repo (see transformations/).
    """
    _sync(session, "smoke")
    session.run("phantasos", "build", "transformations/prisma-browser.py")
    session.run("phantasos", "build", "transformations/adem.py")
```

- [ ] **Step 2: Run the smoke session (proves parity post-migration)**

Run: `uv run nox -s smoke`
Expected output contains:
```
built prisma_browser: imported 427 modules, 0 failures; operations: 95
built adem: imported 110 modules, 0 failures; operations: 13
```

- [ ] **Step 3: Confirm nothing leaked into the repo**

Run: `ls -d prisma-browser-sdk adem-sdk 2>/dev/null || echo OK; ls ../prisma-browser-sdk/adem 2>/dev/null; rm -rf ../prisma-browser-sdk/.phantasos ../adem-sdk/.phantasos`
Expected: `OK` (no generated SDK inside the repo).

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add noxfile.py
git commit -m "wip: add nox smoke session (build example SDKs via OAG)"
```

---

## Task 6: Merge CI workflow (add the build-smoke job) + `.gitignore`

**Files:**
- Modify: `.github/workflows/ci.yml` (append a `smoke` job)
- Modify: `.gitignore` (union with our entries)

- [ ] **Step 1: Append the smoke job to `.github/workflows/ci.yml`**

Add this job under `jobs:` (sibling to `lint`/`tests`/`docs`):

```yaml
  smoke:
    name: Build smoke (OpenAPI Generator)
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
        with:
          persist-credentials: false
      - name: Set up JDK (for OpenAPI Generator)
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: "17"
      - uses: astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5
        with:
          enable-cache: true
      - name: Cache OpenAPI Generator jar
        uses: actions/cache@v4
        with:
          path: ~/.cache/phantasos
          key: oag-jar-7.7.0
      - name: Build example SDKs
        run: uv run nox -s smoke
```

- [ ] **Step 2: Union the `.gitignore`**

Ensure `.gitignore` contains these (append any missing under a `# phantasos` section):

```gitignore
# Secrets — never commit live tenant credentials
.env
.env.*
!.env.example

# Build artifacts
dist/
build/
*.egg-info/

# phantasos per-build preprocess scratch
.phantasos/

# Vendored generator jar (fetched on demand)
.tools/

# macOS
.DS_Store
```

- [ ] **Step 3: Validate the workflow YAML parses**

Run: `uv run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('workflows OK')"`
Expected: `workflows OK` (uses pyyaml if present; otherwise `uvx --from pyyaml python ...`).

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add .github/workflows/ci.yml .gitignore
git commit -m "wip: CI smoke job (JDK + jar cache) + gitignore union"
```

---

## Task 7: Wire the docs (MkDocs nav + real index + reference)

**Files:**
- Modify: `mkdocs.yml` (nav)
- Modify: `docs/index.md` (replace template stub with a real overview)
- Keep: `docs/reference.md` (`::: phantasos`), `docs/ARCHITECTURE.md`, `docs/AUTHORING_A_SPEC.md`, `docs/REARCH_PLAN.md`, `docs/phase-*.md`, `docs/README.md`

- [ ] **Step 1: Replace `docs/index.md` with a real overview**

Write `docs/index.md`:

```markdown
# phantasos

Generate native, self-contained Python SDKs from OpenAPI specs. `phantasos` wraps
[OpenAPI Generator](https://openapi-generator.tech/) and adds generic spec
preprocessing, codegen-bug patches, and vendored, templated components (auth,
pagination, errors, a resource facade) selected per spec.

## Install

```bash
pip install -e ".[generated]"
```

## Build an SDK

```bash
phantasos build transformations/prisma-browser.py
```

See the [Authoring guide](AUTHORING_A_SPEC.md) to onboard a new spec, the
[Architecture](ARCHITECTURE.md) for the design, and the
[API Reference](reference.md) for the `phantasos` package.
```

- [ ] **Step 2: Set the MkDocs nav**

Replace the `nav:` block in `mkdocs.yml` with:

```yaml
nav:
  - Home: index.md
  - Authoring a spec: AUTHORING_A_SPEC.md
  - Architecture: ARCHITECTURE.md
  - API Reference: reference.md
  - Project history:
      - Re-architecture plan: REARCH_PLAN.md
      - Migration phases: README.md
```

- [ ] **Step 3: Build the docs strictly**

Run: `uv run nox -s docs`
Expected: `mkdocs build --strict` succeeds (exit 0). If `--strict` fails on links in the phase docs, fix the broken relative links it names (do not relax `--strict`).

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add mkdocs.yml docs/index.md
git commit -m "wip: MkDocs nav + real index over existing docs"
```

---

## Task 8: Make ruff (lint + format) pass

**Files:** `src/phantasos/*.py`, `transformations/*.py`, `tests/*.py` as ruff reports

- [ ] **Step 1: Auto-format and auto-fix**

```bash
uv run ruff format .
uv run ruff check . --fix
```

- [ ] **Step 2: Run the lint session and fix the remainder by hand**

Run: `uv run nox -s lint`
Expected: PASS. If failures remain, fix each (e.g., add a targeted `# noqa: <code>` only when a rule is a genuine false positive, with a one-line reason). Re-run until green.

- [ ] **Step 3: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: ruff lint + format clean"
```

---

## Task 9: Make mypy (strict) pass

**Files:** `src/phantasos/*.py` (annotations), possibly `pyproject.toml` (extra overrides), `tests/*.py`

- [ ] **Step 1: Run mypy and read the errors**

Run: `uv run nox -s type_check`
Expected initially: FAIL with a list of `error:` lines.

- [ ] **Step 2: Annotate the public surface to satisfy strict**

Add precise type hints to functions/returns in `src/phantasos/` that mypy flags. Guidance:
- `config.py`: dataclasses already typed; add return types where missing.
- `preprocess.py`/`patches.py`/`render.py`/`smoke.py`: annotate params and returns (`dict[str, int]`, `Path`, `list[str]`, etc.).
- `cli.py`: annotate `main(argv: list[str] | None = None) -> int`; the importlib-loaded module is dynamic — type the loaded module as `Any` (`mod: Any = _load_spec_module(...)`).
- For untyped third-party returns (ruamel.yaml), the override in `pyproject.toml` already sets `ignore_missing_imports`; add narrow per-symbol `# type: ignore[no-any-return]` only if strictly needed, with a reason.

- [ ] **Step 3: Re-run until green**

Run: `uv run nox -s type_check`
Expected: `Success: no issues found`.
If a module proves intractable under strict (heavy dynamic behavior), add a *narrow, documented* `[[tool.mypy.overrides]]` for that single module rather than weakening global strictness — and note it in the commit message.

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: mypy strict clean (annotations + narrow overrides)"
```

---

## Task 10: Tests + coverage green

**Files:** `tests/` (possibly add light unit tests to clear the 70% gate)

- [ ] **Step 1: Run the test session with coverage**

Run: `uv run nox -s tests-3.12`
Expected: existing 9 tests pass; a coverage report prints. If `fail_under=70` fails, note which modules are low.

- [ ] **Step 2: Raise coverage cheaply if under 70%**

If under gate, add small unit tests in `tests/` for easy wins:
- `smoke.py`: build a tiny fake package dir in `tmp_path` with one `*_api.py` and assert `smoke()` returns the right `imported`/`operations` counts.
- `cli.py`: write a minimal `sdk.py` in `tmp_path` whose `CONFIG` points at a trivial spec and assert `cli.main(["build", str(path)])` returns an int (monkeypatch `phantasos.generate.generate` to a no-op to avoid Java).

Each as: write test → run `pytest tests/<file>::<test> -v` (expect PASS).

- [ ] **Step 3: Full matrix-equivalent run**

Run: `uv run nox -s tests`
Expected: PASS on every installed Python (3.11–3.14 as available); coverage ≥ 70%.

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: tests + coverage gate green"
```

---

## Task 11: Full `nox` + smoke + lockfile + pre-commit

**Files:** `uv.lock` (committed), `.pre-commit-config.yaml` (from template, verify)

- [ ] **Step 1: Run the entire default suite**

Run: `uv run nox`
Expected: `lint`, `type_check`, `tests`, `docs` all succeed.

- [ ] **Step 2: Run the build-smoke once more**

Run: `uv run nox -s smoke && rm -rf ../prisma-browser-sdk/.phantasos ../adem-sdk/.phantasos`
Expected: prisma 427/0/95, adem 110/0/13.

- [ ] **Step 3: Install + run pre-commit on all files**

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```
Expected: hooks pass (ruff, mypy, codespell, `uv lock --check`, hygiene). Fix any reported issues and re-run.

- [ ] **Step 4: Ensure `uv.lock` is committed**

Run: `git status --short uv.lock`
Expected: `uv.lock` is tracked (commit it if untracked).

- [ ] **Step 5: Commit** (checkpoint)

```bash
git add -A
git commit -m "wip: green nox + smoke + pre-commit; commit uv.lock"
```

---

## Task 12: README badges + follow-ups doc + final polish

**Files:** `README.md`, `TODO.md`

- [ ] **Step 1: Add badges to the top of `README.md`** (right after the `# phantasos` title)

```markdown
[![CI](https://github.com/kaisero/phantasos/actions/workflows/ci.yml/badge.svg)](https://github.com/kaisero/phantasos/actions/workflows/ci.yml)
[![Docs](https://github.com/kaisero/phantasos/actions/workflows/docs.yml/badge.svg)](https://kaisero.github.io/phantasos/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
```

- [ ] **Step 2: Record the Typer-port follow-up in `TODO.md`**

Append:

```markdown

## Follow-up: consider a Typer CLI

The CLI is currently argparse (`phantasos.cli:main`). The project template ships a Typer
scaffold; porting the one `build` command to Typer would add `--help` polish and shell
completion (and align with the template's CLI docs). Tracked as optional; argparse works.
```

- [ ] **Step 3: Update README usage to the production commands** (replace any `uv run --no-project ...` invocation with the installed flow)

Ensure the Quickstart shows:
```bash
uv sync --all-groups
uv run nox             # lint + type-check + tests + docs
uv run nox -s smoke    # build the example SDKs (needs JDK 17)
```

- [ ] **Step 4: Commit** (checkpoint)

```bash
git add README.md TODO.md
git commit -m "wip: README badges + production usage; Typer follow-up note"
```

---

## Task 13: Squash into one commit

**Files:** none (git only)

- [ ] **Step 1: Soft-reset to main, keeping all changes staged**

```bash
git reset --soft main
```

- [ ] **Step 2: Single commit**

```bash
git commit -m "$(cat <<'EOF'
chore: productionize repo from python-project-template

Merge the Copier python-project-template into phantasos for a production setup,
preserving the generator engine and both example specs.

- Copier applied in-place with .copier-answers.yml (future `copier update` works)
- Migrate package to src/phantasos/ layout
- uv + PEP 735 dependency-groups + uv.lock; hatchling (ship *.jinja package data)
- nox single source of truth: lint (ruff), type_check (mypy strict), tests
  (pytest+cov, 70% gate, generate.py excluded), docs (mkdocs --strict), smoke
  (build both example SDKs via OpenAPI Generator)
- GitHub Actions: CI matrix + JDK17 build-smoke job, docs (Pages), release
  (PyPI Trusted Publishing), audit, CodeQL, Dependabot
- MkDocs Material + mkdocstrings; curated nav over existing docs
- Apache-2.0 LICENSE; pre-commit; CONTRIBUTING/SECURITY/CHANGELOG
- CLI stays argparse (Typer port noted as follow-up in TODO.md)

Verified: nox (lint/type/tests/docs) green; nox -s smoke -> prisma 427/0/95,
adem 110/0/13; pre-commit --all-files green; nothing generated inside the repo.
EOF
)"
```

- [ ] **Step 3: Confirm a single clean commit ahead of main**

Run: `git log --oneline main..HEAD`
Expected: exactly one commit (the chore above).

- [ ] **Step 4: Final verification from a clean state**

```bash
git status --short | grep -v fuse_hidden || echo "(clean)"
uv run nox && uv run nox -s smoke && rm -rf ../prisma-browser-sdk/.phantasos ../adem-sdk/.phantasos
```
Expected: clean tree; full nox + smoke all green.

The branch `chore/productionize-template` is now ready to merge into `main`.

---

## Self-Review (completed during planning)

**Spec coverage:** every grilled decision maps to a task — mechanism/branch/squash (Tasks 0,1,13); src layout (3); CLI argparse + follow-up (4 scripts, 12 note); mypy strict (4 config, 9); coverage 70% + exclude glue (4 config, 10); smoke session + CI Java job (5, 6); MkDocs nav + history (7); metadata values (1); conflict matrix (2, 4, 6, 7, 12). ✓

**Placeholder scan:** all file contents (pyproject, conftest, nox session, CI job, gitignore, index.md, nav, badges) are given verbatim; Tasks 8–10 are inherently "fix what the tool reports" but each gives the exact command, the strategy, and the green criterion rather than a vague "handle errors." ✓

**Type/name consistency:** package import name `phantasos`; dist/slug `phantasos`; console script `phantasos.cli:main`; coverage `source=["phantasos"]` with `omit=["src/phantasos/generate.py"]`; hatchling `packages=["src/phantasos"]` — consistent across tasks. ✓

**Known risks:**
- Copier local-path application may need the template committed at HEAD (`--vcs-ref=HEAD`) — Task 1 notes this.
- mypy strict on dynamic `cli.py` may need a narrow override — Task 9 Step 3 allows it, documented.
- `mkdocs build --strict` may flag stale relative links in the historical phase docs — Task 7 Step 3 says fix the links, not relax strict.
