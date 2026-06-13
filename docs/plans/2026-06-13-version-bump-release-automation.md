# Version-bump-triggered Release Automation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a new `pyproject.toml` version landing on `main` automatically build, publish to PyPI (Trusted Publishing), and create a GitHub Release from the matching `CHANGELOG.md` section — for phantasos itself and for every generated SDK/CLI project (the scaffold template).

**Architecture:** One self-contained `release.yml` (filename + `environment: pypi` preserved for the pinned PyPI Trusted Publisher). Trigger on `push: main` + `workflow_dispatch`. A `check` job reads the version, gates on whether `v<version>` is already released (`gh release view`), and fails fast if the CHANGELOG section is missing; then `build` → `publish` (`skip-existing`) → `release` (`gh release create` makes the tag + Release, attaches sdist+wheel). The scaffold template mirrors it. Ship phantasos as `0.1.0a1` (PEP 440 alpha → auto pre-release) as the e2e test on merge.

**Tech Stack:** GitHub Actions, uv, `pypa/gh-action-pypi-publish` (OIDC), `gh` CLI, awk/tomllib/`packaging`. Design doc: `docs/specs/2026-06-13-version-bump-release-automation-design.md`.

**Branch:** all work on `release-automation` (already created from `main`), delivered via PR to `main`.

**Note on testing:** workflow logic can't be unit-tested, but each task has real validation — `uv lock --check`, YAML parse, the inline gate snippets exercised locally, and the existing scaffold test `tests/test_scaffold.py::test_builtin_workflows_render_valid_yaml` (renders every workflow template and parses it as YAML). The true e2e test is merging the PR.

---

## Task 1: Bump version to `0.1.0a1` (pyproject + CHANGELOG + lock)

**Files:**
- Modify: `pyproject.toml:3`
- Modify: `CHANGELOG.md:10,37,38` (+ add line 39 ref)
- Modify: `uv.lock` (via `uv lock`)

- [ ] **Step 1: Bump the pyproject version**

In `pyproject.toml`, change line 3:
```toml
version = "0.1.0"
```
to:
```toml
version = "0.1.0a1"
```

- [ ] **Step 2: Rename the CHANGELOG heading**

In `CHANGELOG.md`, change line 10:
```markdown
## [0.1.0] - 2026-06-13
```
to:
```markdown
## [0.1.0a1] - 2026-06-13
```

- [ ] **Step 3: Fix the CHANGELOG link-ref ladder**

In `CHANGELOG.md`, replace these two lines:
```markdown
[Unreleased]: https://github.com/kaisero/phantasos/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kaisero/phantasos/compare/v0.0.1...v0.1.0
```
with:
```markdown
[Unreleased]: https://github.com/kaisero/phantasos/compare/v0.1.0a1...HEAD
[0.1.0a1]: https://github.com/kaisero/phantasos/compare/v0.0.1...v0.1.0a1
```
(Leave the `[0.0.1]: …/releases/tag/v0.0.1` line unchanged.)

- [ ] **Step 4: Re-lock so `uv.lock` matches (CI runs `uv lock --check`)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv lock`
Then verify: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv lock --check`
Expected: exits 0 (lock in sync); `uv.lock` now shows `version = "0.1.0a1"` for the `phantasos` package.

- [ ] **Step 5: Verify the gate snippet now resolves the new version + notes**

Run:
```bash
uv run --no-project --with packaging python -c "import tomllib; from packaging.version import Version; v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; print(v, str(Version(v).is_prerelease).lower())"
awk -v ver="0.1.0a1" '/^## \[/ { if (found) exit; if (index($0, "[" ver "]")) { found=1; next } } found { print }' CHANGELOG.md | sed -e '/./,$!d' | head -3
```
Expected: first line prints `0.1.0a1 true`; the awk prints the `### Added` block (non-empty).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml CHANGELOG.md uv.lock
git commit -m "chore: bump version to 0.1.0a1 (PEP 440 alpha)"
```

---

## Task 2: Rewrite `.github/workflows/release.yml` (model A)

**Files:**
- Replace: `.github/workflows/release.yml`

- [ ] **Step 1: Replace the workflow with the version-bump-triggered design**

Overwrite `.github/workflows/release.yml` with exactly:

```yaml
name: Release

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: release
  cancel-in-progress: false

jobs:
  check:
    name: Detect unreleased version
    runs-on: ubuntu-latest
    timeout-minutes: 10
    outputs:
      release: ${{ steps.gate.outputs.release }}
      version: ${{ steps.gate.outputs.version }}
      prerelease: ${{ steps.gate.outputs.prerelease }}
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Resolve version, gate on existing release, extract notes
        id: gate
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          OUT=$(uv run --no-project --with packaging python -c "import tomllib; from packaging.version import Version; v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; nv=str(Version(v)); assert nv==v, 'pyproject version '+v+' not PEP440-canonical; use '+nv; print(v); print(str(Version(v).is_prerelease).lower())")
          VERSION=$(printf '%s\n' "$OUT" | sed -n 1p)
          PRERELEASE=$(printf '%s\n' "$OUT" | sed -n 2p)
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "prerelease=$PRERELEASE" >> "$GITHUB_OUTPUT"
          echo "Resolved version v$VERSION (prerelease=$PRERELEASE)"
          if gh release view "v$VERSION" >/dev/null 2>&1; then
            echo "v$VERSION already released; nothing to do."
            echo "release=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          awk -v ver="$VERSION" '/^## \[/ { if (found) exit; if (index($0, "[" ver "]")) { found=1; next } } found { print }' CHANGELOG.md | sed -e '/./,$!d' > notes.md
          if ! grep -q '[^[:space:]]' notes.md; then
            echo "::error::Missing CHANGELOG.md section '## [$VERSION]'. Add release notes before bumping the version."
            exit 1
          fi
          echo "release=true" >> "$GITHUB_OUTPUT"
      - name: Upload release notes
        if: steps.gate.outputs.release == 'true'
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: release-notes
          path: notes.md

  build:
    name: Build distributions
    needs: check
    if: needs.check.outputs.release == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Build sdist and wheel
        run: uv build
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment:
      name: pypi
      url: https://pypi.org/p/${{ github.event.repository.name }}
    permissions:
      id-token: write  # PyPI Trusted Publishing (OIDC) + attestations
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - name: Publish
        uses: pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # release/v1
        with:
          attestations: true  # PEP 740 build provenance
          skip-existing: true  # idempotent if a retry re-runs after a successful upload

  release:
    name: Create GitHub Release
    needs: [check, publish]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write  # create the tag + GitHub Release
    env:
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: release-notes
          path: .
      - name: Create GitHub Release (tag + notes + assets)
        shell: bash
        run: |
          set -euo pipefail
          VERSION="${{ needs.check.outputs.version }}"
          FLAGS=()
          if [ "${{ needs.check.outputs.prerelease }}" = "true" ]; then
            FLAGS+=(--prerelease)
          fi
          gh release create "v$VERSION" \
            --target "$GITHUB_SHA" \
            --title "v$VERSION" \
            --notes-file notes.md \
            "${FLAGS[@]}" \
            dist/*
```

- [ ] **Step 2: Validate it parses as YAML**

Run: `uv run --no-project --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('release.yml OK')"`
Expected: `release.yml OK` (no exception).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: release on version bump to main (PyPI + GitHub Release from CHANGELOG)"
```

---

## Task 3: Mirror the design into the scaffold template

**Files:**
- Replace: `src/phantasos/scaffold/.github/workflows/release.yml.jinja`
- Test: `tests/test_scaffold.py::test_builtin_workflows_render_valid_yaml` (existing)

- [ ] **Step 1: Replace the template**

Overwrite `src/phantasos/scaffold/.github/workflows/release.yml.jinja` with exactly (note: the whole file is wrapped in `{% raw %}` so Jinja leaves the `${{ … }}` GitHub expressions alone; the single break-out is `{{ distribution }}` for the PyPI URL):

```jinja
{% raw %}name: Release

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: release
  cancel-in-progress: false

jobs:
  check:
    name: Detect unreleased version
    runs-on: ubuntu-latest
    timeout-minutes: 10
    outputs:
      release: ${{ steps.gate.outputs.release }}
      version: ${{ steps.gate.outputs.version }}
      prerelease: ${{ steps.gate.outputs.prerelease }}
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Resolve version, gate on existing release, extract notes
        id: gate
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          OUT=$(uv run --no-project --with packaging python -c "import tomllib; from packaging.version import Version; v=tomllib.load(open('pyproject.toml','rb'))['project']['version']; nv=str(Version(v)); assert nv==v, 'pyproject version '+v+' not PEP440-canonical; use '+nv; print(v); print(str(Version(v).is_prerelease).lower())")
          VERSION=$(printf '%s\n' "$OUT" | sed -n 1p)
          PRERELEASE=$(printf '%s\n' "$OUT" | sed -n 2p)
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "prerelease=$PRERELEASE" >> "$GITHUB_OUTPUT"
          echo "Resolved version v$VERSION (prerelease=$PRERELEASE)"
          if gh release view "v$VERSION" >/dev/null 2>&1; then
            echo "v$VERSION already released; nothing to do."
            echo "release=false" >> "$GITHUB_OUTPUT"
            exit 0
          fi
          awk -v ver="$VERSION" '/^## \[/ { if (found) exit; if (index($0, "[" ver "]")) { found=1; next } } found { print }' CHANGELOG.md | sed -e '/./,$!d' > notes.md
          if ! grep -q '[^[:space:]]' notes.md; then
            echo "::error::Missing CHANGELOG.md section '## [$VERSION]'. Add release notes before bumping the version."
            exit 1
          fi
          echo "release=true" >> "$GITHUB_OUTPUT"
      - name: Upload release notes
        if: steps.gate.outputs.release == 'true'
        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: release-notes
          path: notes.md

  build:
    name: Build distributions
    needs: check
    if: needs.check.outputs.release == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3
        with:
          persist-credentials: false
      - uses: astral-sh/setup-uv@fac544c07dec837d0ccb6301d7b5580bf5edae39 # v8.2.0
        with:
          enable-cache: true
      - name: Build sdist and wheel
        run: uv build
      - uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1
        with:
          name: dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    timeout-minutes: 15
    environment:
      name: pypi
      url: https://pypi.org/p/{% endraw %}{{ distribution }}{% raw %}
    permissions:
      id-token: write  # PyPI Trusted Publishing (OIDC) + attestations
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - name: Publish
        uses: pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # release/v1
        with:
          attestations: true  # PEP 740 build provenance
          skip-existing: true  # idempotent if a retry re-runs after a successful upload

  release:
    name: Create GitHub Release
    needs: [check, publish]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write  # create the tag + GitHub Release
    env:
      GH_TOKEN: ${{ github.token }}
      GH_REPO: ${{ github.repository }}
    steps:
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: dist
          path: dist/
      - uses: actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1
        with:
          name: release-notes
          path: .
      - name: Create GitHub Release (tag + notes + assets)
        shell: bash
        run: |
          set -euo pipefail
          VERSION="${{ needs.check.outputs.version }}"
          FLAGS=()
          if [ "${{ needs.check.outputs.prerelease }}" = "true" ]; then
            FLAGS+=(--prerelease)
          fi
          gh release create "v$VERSION" \
            --target "$GITHUB_SHA" \
            --title "v$VERSION" \
            --notes-file notes.md \
            "${FLAGS[@]}" \
            dist/*
{% endraw %}
```

- [ ] **Step 2: Render + YAML-validate the template via the existing scaffold test**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python -m pytest tests/test_scaffold.py::test_builtin_workflows_render_valid_yaml -q -p no:cacheprovider --no-header`
Expected: PASS (the rendered `release.yml` is valid YAML; `{{ distribution }}` interpolated, all `${{ }}` preserved).

- [ ] **Step 3: Eyeball the rendered output once**

Run:
```bash
UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv uv run --no-sync python - <<'PY'
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
d = Path("src/phantasos/scaffold/.github/workflows")
env = Environment(loader=FileSystemLoader(str(d)), keep_trailing_newline=True, undefined=StrictUndefined)
out = env.get_template("release.yml.jinja").render(distribution="acme-sdk")
print(out)
PY
```
Expected: the PyPI URL line reads `url: https://pypi.org/p/acme-sdk`, and every `${{ … }}` GitHub expression is present verbatim (NOT blanked out).

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/scaffold/.github/workflows/release.yml.jinja
git commit -m "ci(scaffold): generated projects auto-release on version bump (matches host workflow)"
```

---

## Task 4: Offline gate + open the PR (merge = e2e test)

**Files:** none (verification + delivery)

- [ ] **Step 1: Full offline gate (managed pythons)**

Run: `UV_PROJECT_ENVIRONMENT=/tmp/phantasos-uv NOX_ENVDIR=/tmp/phantasos-nox UV_PYTHON_PREFERENCE=only-managed uv run nox --envdir /tmp/phantasos-nox`
Expected: `lint`, `type_check`, `tests` (3.11–3.14), `docs` all succeed. (Confirms the version bump + scaffold template change didn't break the suite or `uv lock --check`.)

- [ ] **Step 2: Push the branch**

```bash
git push "https://x-access-token:$(gh auth token)@github.com/kaisero/phantasos.git" HEAD:release-automation
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create --base main --head release-automation \
  --title "ci: version-bump-triggered release (PyPI + GitHub Release from CHANGELOG); ship 0.1.0a1" \
  --body "See docs/specs/2026-06-13-version-bump-release-automation-design.md. Merging this PR is the e2e test: push-to-main runs the new release.yml, sees 0.1.0a1 as unreleased, and publishes it (PyPI pre-release + GitHub pre-release with CHANGELOG notes, sdist+wheel attached). Also applies the same model to the scaffold template for generated SDK/CLI projects."
```

- [ ] **Step 4: Confirm PR CI is green, then it's ready to merge**

Run: `gh pr checks <PR#>` (wait for completion). Expected: all checks pass (the `release.yml` does NOT run on the PR — only on push-to-main — so no premature publish).

- [ ] **Step 5 (operator, post-merge): observe the e2e release**

After merge, watch the `Release` workflow run on `main`: `check` → `build` → `publish` (PyPI; may pause if the `pypi` environment has an approval gate) → `release`. Confirm `phantasos 0.1.0a1` appears on PyPI as a pre-release and the GitHub Release `v0.1.0a1` (pre-release) carries the CHANGELOG notes + sdist/wheel assets.

---

## Self-review checklist

- [ ] **Spec coverage:** trigger+gate (T2/T3 `check`), idempotency via `gh release view` + `skip-existing` (T2/T3), fail-fast on missing CHANGELOG (T2/T3 `check`), build/publish/release DAG (T2/T3), PEP 440 prerelease flag (T2/T3 `release`), attach sdist+wheel (T2/T3 `release`), scaffold parity (T3), `0.1.0a1` version + CHANGELOG + lock (T1), branch→PR→merge e2e (T4). All mapped.
- [ ] **No placeholders:** full workflow YAML given verbatim in T2 and T3; exact line edits in T1; exact validation commands with expected output.
- [ ] **Consistency:** `release.yml` filename + `environment: pypi` preserved (Trusted Publisher pin); job outputs `release`/`version`/`prerelease` referenced identically in `build`/`publish`/`release`; host workflow uses `${{ github.event.repository.name }}` for the PyPI URL while the template uses `{{ distribution }}` — the only host/template difference.
