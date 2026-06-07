# Rename `sdkgen` → `phantasos` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the project from `sdkgen` to `phantasos` across the entire tracked source tree — package, imports, CLI, env vars, cache path, URLs, docs, tests, and templates.

**Architecture:** A scripted, ordered sweep. Move the package directory with `git mv` (preserving history), then apply two case-sensitive content substitutions (`sdkgen`→`phantasos`, `SDKGEN`→`PHANTASOS`) to tracked text files only, excluding generated/cache artifacts and `uv.lock`. Regenerate `uv.lock` with `uv lock`. The existing test suite is the verification gate — there is no new behavior to test-drive.

**Tech Stack:** Python 3.11+, uv, nox, pytest, hatchling, git.

---

### Task 1: Move the package directory

**Files:**
- Move: `src/sdkgen/` → `src/phantasos/`

- [ ] **Step 1: Confirm clean-ish starting state**

Run: `git status --short | grep -v fuse_hidden`
Expected: only the pre-existing deletions/untracked files from session start; no surprises. Note them so they aren't confused with rename changes.

- [ ] **Step 2: Move the package dir with history preserved**

Run: `git mv src/sdkgen src/phantasos`

- [ ] **Step 3: Verify the move**

Run: `ls src/ && git status --short | grep -E 'src/(sdkgen|phantasos)' | head`
Expected: `src/phantasos` exists, `src/sdkgen` gone; git shows renames (`R`) for the moved files.

- [ ] **Step 4: Commit the move**

```bash
git add -A
git commit -m "refactor: move src/sdkgen to src/phantasos"
```

---

### Task 2: Rewrite tracked file contents

**Files:**
- Modify: all tracked text files containing `sdkgen` or `SDKGEN`, EXCEPT `uv.lock` (regenerated in Task 3).

- [ ] **Step 1: List the files that will change (dry run)**

Run:
```bash
git ls-files -z | grep -zZv 'uv.lock' \
  | xargs -0 grep -Il -e 'sdkgen' -e 'SDKGEN' 2>/dev/null
```
Expected: the source/doc/test/template files (e.g. `pyproject.toml`, `README.md`, `mkdocs.yml`, `noxfile.py`, `.copier-answers.yml`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `src/phantasos/*.py`, `src/phantasos/components/**/*.jinja`, `tests/*.py`, `transformations/*.py`, `docs/*.md`). NOT `uv.lock`, NOT anything under `.git/` or a `*_cache/`.

- [ ] **Step 2: Apply the two case-sensitive substitutions**

Run:
```bash
git ls-files -z | grep -zZv 'uv.lock' \
  | xargs -0 grep -Il -e 'sdkgen' -e 'SDKGEN' 2>/dev/null \
  | xargs -r sed -i -e 's/sdkgen/phantasos/g' -e 's/SDKGEN/PHANTASOS/g'
```
This renames the PyPI/package name, all imports, the CLI entry `sdkgen = "sdkgen.cli:main"` → `phantasos = "phantasos.cli:main"`, env vars `SDKGEN_CACHE`/`SDKGEN_VERSION` → `PHANTASOS_*`, the `~/.cache/sdkgen` default, and `kaisero/sdkgen` URLs → `kaisero/phantasos`.

- [ ] **Step 3: Fix stale `sdk-gen` path references in the old plan doc**

The historical plan references the no-longer-existing path `git/sdk-gen`. Step 2 already turned `sdkgen`→`phantasos` but the hyphenated `sdk-gen` path remains.

Run:
```bash
sed -i 's#git/sdk-gen#git/pan-sdk-generator#g; s/sdk-gen/phantasos/g' \
  docs/superpowers/plans/2026-06-07-productionize-sdkgen.md
```

- [ ] **Step 4: Rename the old plan doc file**

Run: `git mv docs/superpowers/plans/2026-06-07-productionize-sdkgen.md docs/superpowers/plans/2026-06-07-productionize-phantasos.md`

- [ ] **Step 5: Verify zero remaining old-name hits (excluding uv.lock)**

Run:
```bash
grep -rIin -e 'sdkgen' -e 'sdk-gen' -e 'sdk_gen' -e 'SDKGEN' . \
  --exclude-dir=.git --exclude='uv.lock' \
  | grep -v '_cache/' | grep -v '__pycache__'
```
Expected: **no output** (exit status 1). If anything prints, inspect and fix it (e.g. a mixed-case form or a file `git ls-files` didn't cover) before continuing.

- [ ] **Step 6: Sanity-check key files**

Run: `grep -n 'phantasos' pyproject.toml | head; grep -n 'name =' .copier-answers.yml 2>/dev/null; grep -rn 'PHANTASOS_CACHE' src/phantasos/generate.py`
Expected: `name = "phantasos"`, `phantasos = "phantasos.cli:main"`, `packages = ["src/phantasos"]`, `PHANTASOS_CACHE` in generate.py, copier `package_name: phantasos` etc.

- [ ] **Step 7: Commit the content rewrite**

```bash
git add -A
git commit -m "refactor: rename sdkgen to phantasos across the codebase"
```

---

### Task 3: Regenerate the lockfile

**Files:**
- Modify: `uv.lock`

- [ ] **Step 1: Regenerate the lock**

Run: `uv lock`
Expected: `uv.lock` updates so the local project's own package entry is `name = "phantasos"`. (If `uv lock` errors on the renamed package, read the error — it usually means a `pyproject.toml` reference was missed; fix and re-run.)

- [ ] **Step 2: Confirm no `sdkgen` left in the lock's project metadata**

Run: `grep -n 'sdkgen' uv.lock || echo "clean"`
Expected: `clean` (or, at most, only references that legitimately belong to unrelated upstream packages — there should be none, since `sdkgen` is the project's own name).

- [ ] **Step 3: Commit the lockfile**

```bash
git add uv.lock
git commit -m "chore: regenerate uv.lock for phantasos rename"
```

---

### Task 4: Verify the rename end-to-end

**Files:** none (verification only).

- [ ] **Step 1: Import the renamed package**

Run: `uv run --no-project --python 3.12 --with jinja2 --with ruamel.yaml python -c "import sys; sys.path.insert(0,'src'); import phantasos; print(phantasos.__file__)"`
Expected: prints a path under `src/phantasos/__init__.py`, no ImportError.

- [ ] **Step 2: Run the full test suite**

Run: `nox` (or, if nox sessions are slow/unavailable: `uv run pytest -q`)
Expected: all tests pass. The suite exercises the CLI, config, render, and a smoke build of the example specs — so a green run confirms the rename didn't break imports, the entry point, env-var handling, or template rendering.

- [ ] **Step 3: Final grep gate**

Run:
```bash
grep -rIin -e 'sdkgen' -e 'sdk-gen' -e 'sdk_gen' -e 'SDKGEN' . \
  --exclude-dir=.git --exclude='uv.lock' \
  | grep -v '_cache/' | grep -v '__pycache__' || echo "ALL CLEAR"
```
Expected: `ALL CLEAR`.

- [ ] **Step 4: Final review of the spec vs. result**

Re-open `docs/superpowers/specs/2026-06-07-rename-sdkgen-to-phantasos-design.md` and confirm every row of the name-mapping table is satisfied. If all green, the rename is complete.

---

## Notes for the executor

- **Why not blind `sed -i` over the whole tree?** It would corrupt `uv.lock` hashes and touch binary/cache files. Driving substitutions off `git ls-files` keeps it to tracked text files.
- **No git remote** is configured (`git remote -v` is empty), so there is no remote URL to update — only in-code URL strings change.
- **Renaming the working-directory folder** (`pan-sdk-generator`) and the **GitHub repo** itself are explicitly out of scope (see spec).
