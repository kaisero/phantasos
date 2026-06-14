# Design: Rename `sdkgen` → `phantasos`

**Date:** 2026-06-07
**Status:** Approved

## Goal

Rename the project from `sdkgen` (formerly `sdk-gen`) to `phantasos` everywhere —
package/import name, PyPI distribution name, CLI command, environment variables,
runtime cache path, repository URLs, documentation, tests, and templates. After
this change no form of the old name (`sdkgen`, `sdk-gen`, `sdk_gen`, `SDKGEN`)
remains in the tracked source tree (excluding `uv.lock`, which is regenerated).

## Name mapping

| Old form | New form | Locations |
|---|---|---|
| `sdkgen` (package / import / module) | `phantasos` | `src/sdkgen/` directory; all `import sdkgen` / `from sdkgen …`; CLI script entry point `sdkgen = "sdkgen.cli:main"` |
| `name = "sdkgen"` (PyPI distribution) | `phantasos` | `pyproject.toml`, `.copier-answers.yml` (`package_name`, `project_name`, `project_slug`) |
| `SDKGEN_CACHE`, `SDKGEN_VERSION` | `PHANTASOS_CACHE`, `PHANTASOS_VERSION` | `src/sdkgen/generate.py`, `src/sdkgen/__init__.py` (generated `_about.py` template), `README.md`, `docs/AUTHORING_A_SPEC.md` |
| `~/.cache/sdkgen` | `~/.cache/phantasos` | `src/sdkgen/generate.py` runtime default |
| `kaisero/sdkgen` (URLs) | `kaisero/phantasos` | `pyproject.toml` `[project.urls]`, `mkdocs.yml`, docs |
| `sdk-gen` / `git/sdk-gen` (prose + paths) | `phantasos` / `git/pan-sdk-generator` | `docs/plans/2026-06-07-productionize-sdkgen.md` |

Casing is handled with two case-sensitive passes: `sdkgen` → `phantasos` and
`SDKGEN` → `PHANTASOS`. No mixed-case variants (`SdkGen`, `Sdkgen`, etc.) exist
in the tree (verified via grep), so no additional passes are needed.

## Approach

A careful, scripted sweep — not a blind recursive `sed`:

1. **Move the package directory** with `git mv src/sdkgen src/phantasos` to
   preserve file history.
2. **Rewrite file contents** across tracked text files with two case-sensitive
   substitutions (`sdkgen`→`phantasos`, `SDKGEN`→`PHANTASOS`). Exclude generated
   and cache artifacts: `.git/`, `*_cache/` (`.mypy_cache`, `.ruff_cache`,
   `.pytest_cache`), `__pycache__/`, `.coverage`, and **`uv.lock`**. Operate on
   `git ls-files` output so only tracked files are touched.
3. **Fix stale paths in the old plan doc**: replace `git/sdk-gen` references with
   `git/pan-sdk-generator` (that path no longer exists), apply the name
   substitutions, and `git mv` the file to
   `2026-06-07-productionize-phantasos.md`.
4. **Regenerate `uv.lock`** via `uv lock` so the local project's own metadata
   entry (`name = "phantasos"`) updates with valid hashes, rather than editing
   the lockfile by hand.
5. **Git remote**: there is currently no `origin` remote configured
   (`git remote -v` is empty), so no remote URL change is required. The in-code
   repository URLs are still updated to `kaisero/phantasos` per step 2.

## Verification

- `grep -rIi -e 'sdkgen' -e 'sdk-gen' -e 'sdk_gen' . --exclude-dir=.git --exclude='uv.lock'`
  returns **zero** hits.
- The package directory is `src/phantasos/` and `src/sdkgen/` no longer exists.
- `uv run python -c "import phantasos; print(phantasos.__file__)"` succeeds.
- The CLI entry point resolves: `uv run phantasos --help` (or equivalent) works.
- The test suite passes: `nox` / `pytest` (exercises CLI, config, render, smoke
  build of the example specs).

## Out of scope

- Renaming the local working-directory folder. It is already
  `pan-sdk-generator`; renaming the current working directory mid-session is
  disruptive and unnecessary for the rename.
- Renaming the actual GitHub repository on github.com. That is a UI/admin action
  the user performs; this change only updates URL strings in the codebase.
