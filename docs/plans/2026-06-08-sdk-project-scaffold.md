# SDK Project Scaffolding (Phase C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every generated SDK a phantasos-grade project — suppress OpenAPI Generator's scaffolding and render a curated, value-substituted project (pyproject, CI/CD, pre-commit, behavioral tests) from version-controlled templates that survive regeneration.

**Architecture:** A new `scaffold.py` renders a built-in `src/phantasos/scaffold/` template tree plus per-product `products/<product>/overrides/` (same-path-wins) into the SDK root using the unified context (now including a typed `project:` block). phantasos writes a `.openapi-generator-ignore` before generation to suppress OAG's files; the isolated smoke check installs via `pip install <project_dir>`.

**Tech Stack:** Python 3.11+, pydantic v2, jinja2, ruamel.yaml, pytest, nox, ruff, mypy. Builds on `declarative-products-config`. Design: `docs/specs/2026-06-08-sdk-project-scaffold-design.md`.

---

## Confirmed decisions
1. Built-in `src/phantasos/scaffold/` + per-product `products/<product>/overrides/` (same-path replaces built-in). SDK fully overwritten each build.
2. Typed `project:` block in `sdk.yml` (distribution/description/author/author_email/repo_url required-ish; license default Apache-2.0; python_versions default phantasos matrix; optional `dependencies`).
3. Base deps default: `urllib3>=2.1.0,<3.0.0`, `python-dateutil>=2.8.2`, `pydantic>=2.11`, `typing-extensions>=4.7.1`.
4. OAG suppression via phantasos-written `.openapi-generator-ignore`. Smoke → `pip install <project_dir>`.
5. README always per-product (`overrides/README.md.jinja`). Component tests built-in (gated on `has_*`); model tests per-product.
6. Scaffold set: pyproject, nox, pre-commit, ci, release, audit, secrets, codeql, docs/mkdocs, meta files.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/productconfig.py` | add `ProjectConfig` model + `project:` on `ProductConfig`; auto-expose `project.*` (flattened) in `load_product` context | Modify |
| `src/phantasos/scaffold.py` | render built-in scaffold + overrides → SDK root | **Create** |
| `src/phantasos/generate.py` | write `.openapi-generator-ignore` before invoking OAG | Modify |
| `src/phantasos/__init__.py` | call scaffold step (after vendor) | Modify |
| `src/phantasos/smoke.py` | `_ensure_smoke_venv`: `pip install <project_dir>` (needs `pyproject.toml`, not `requirements.txt`) | Modify |
| `src/phantasos/scaffold/**` | the ~14 built-in templates + `tests/` component tests | **Create** |
| `products/{adem,prisma-browser}/sdk.yml` | add `project:` block | Modify |
| `products/{adem,prisma-browser}/overrides/**` | `README.md.jinja` (+ prisma `tests/test_models.py.jinja`) | **Create** |
| `pyproject.toml` | ship `scaffold/**` as package data | Modify |
| `docs/ONBOARDING.md` | the generate-once→learn-deps flow | **Create** |
| `tests/test_scaffold.py`, `tests/test_productconfig.py`, `tests/test_smoke.py` | new/updated tests | Create/Modify |

---

### Task 1: `project:` block + base deps + auto-exposed context

**Files:** Modify `src/phantasos/productconfig.py`; Test `tests/test_productconfig.py`.

- [ ] **Step 1: Write failing tests** (append to `tests/test_productconfig.py`)

```python
from phantasos.productconfig import ProjectConfig  # noqa: E402


def test_project_defaults() -> None:
    p = ProjectConfig(distribution="acme-sdk", author="A", author_email="a@b.c",
                      repo_url="https://github.com/x/acme-sdk")
    assert p.license == "Apache-2.0"
    assert p.python_versions == ["3.11", "3.12", "3.13", "3.14"]
    assert "pydantic >= 2.11" in p.dependencies


def test_project_block_in_sdk_yml(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {title: Acme, version: '9'}\npaths: {}\n", "utf-8")
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, "
        "repo_url: https://github.com/x/acme-sdk}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.config.project.distribution == "acme-sdk"
    # project.* is auto-exposed (flattened) to the template context
    assert loaded.context["distribution"] == "acme-sdk"
    assert loaded.context["repo_url"] == "https://github.com/x/acme-sdk"
    assert loaded.context["license"] == "Apache-2.0"
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_productconfig.py -k project -q`
Expected: FAIL — `ImportError: cannot import name 'ProjectConfig'`.

- [ ] **Step 3: Implement.** In `productconfig.py` add the model and field, and extend the context + `_AUTO_EXPOSED` in `load_product`:

```python
_BASE_DEPS = [
    "urllib3 >= 2.1.0, < 3.0.0",
    "python-dateutil >= 2.8.2",
    "pydantic >= 2.11",
    "typing-extensions >= 4.7.1",
]


class ProjectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    distribution: str
    author: str
    author_email: str
    repo_url: str
    description: str = ""
    license: str = "Apache-2.0"
    python_versions: list[str] = Field(
        default_factory=lambda: ["3.11", "3.12", "3.13", "3.14"]
    )
    dependencies: list[str] = Field(default_factory=lambda: list(_BASE_DEPS))
```

Add to `ProductConfig`: `project: ProjectConfig | None = None`.

In `load_product`, after building `context` and before the vars-collision check, add the
flattened project fields and extend `_AUTO_EXPOSED`:
```python
    if cfg.project is not None:
        context.update(
            {
                "distribution": cfg.project.distribution,
                "description": cfg.project.description,
                "author": cfg.project.author,
                "author_email": cfg.project.author_email,
                "repo_url": cfg.project.repo_url,
                "license": cfg.project.license,
                "python_versions": cfg.project.python_versions,
                "dependencies": cfg.project.dependencies,
            }
        )
```
And add those keys to the module-level `_AUTO_EXPOSED` set:
`"distribution", "description", "author", "author_email", "repo_url", "license", "python_versions", "dependencies"`.

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml pytest tests/test_productconfig.py -q`
Expected: PASS (all productconfig tests).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/productconfig.py tests/test_productconfig.py
git commit -m "feat(productconfig): typed project block + base deps + auto-exposed project.* context"
```

---

### Task 2: `.openapi-generator-ignore` writer (suppress OAG scaffolding)

**Files:** Modify `src/phantasos/generate.py`; Test `tests/test_generate.py`.

- [ ] **Step 1: Write failing test** (append to `tests/test_generate.py`)

```python
def test_write_ignore_lists_suppressed_files(tmp_path: Path) -> None:
    from phantasos import generate

    generate.write_openapi_generator_ignore(tmp_path)
    text = (tmp_path / ".openapi-generator-ignore").read_text(encoding="utf-8")
    for f in ("setup.py", "requirements.txt", "tox.ini", "git_push.sh",
              ".gitlab-ci.yml", ".travis.yml", ".github/workflows/python.yml", "README.md"):
        assert f in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ignore -q`
Expected: FAIL — `AttributeError: ... has no attribute 'write_openapi_generator_ignore'`.

- [ ] **Step 3: Implement in `generate.py`**

```python
_OAG_IGNORE = [
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "test-requirements.txt",
    "tox.ini",
    "git_push.sh",
    ".gitlab-ci.yml",
    ".travis.yml",
    ".github/workflows/python.yml",
    "README.md",
]


def write_openapi_generator_ignore(out_dir: Path) -> None:
    """Suppress OAG's supporting files so phantasos's scaffold owns them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    body = "# Written by phantasos — these are provided by the project scaffold.\n"
    body += "\n".join(_OAG_IGNORE) + "\n"
    (out_dir / ".openapi-generator-ignore").write_text(body, encoding="utf-8")
```
(Add `from pathlib import Path` if not present — it is.)

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_generate.py -k ignore -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/generate.py tests/test_generate.py
git commit -m "feat(generate): write .openapi-generator-ignore to suppress OAG scaffolding"
```

---

### Task 3: Scaffold engine (`scaffold.py`)

**Files:** Create `src/phantasos/scaffold.py`; Test `tests/test_scaffold.py`.

- [ ] **Step 1: Write failing tests** — create `tests/test_scaffold.py`

```python
"""Tests for the project-scaffold renderer."""

from pathlib import Path

from phantasos import scaffold


def _ctx(**over):
    base = {"package": "acme", "distribution": "acme-sdk", "has_auth": True,
            "has_pagination": False, "repo_url": "https://x/acme-sdk"}
    base.update(over)
    return base


def test_scaffold_renders_builtin_and_strips_jinja(tmp_path: Path) -> None:
    builtin = tmp_path / "scaffold"
    (builtin / ".github" / "workflows").mkdir(parents=True)
    (builtin / "pyproject.toml.jinja").write_text("name = '{{ distribution }}'\n", "utf-8")
    (builtin / ".github" / "workflows" / "ci.yml.jinja").write_text("on: [push]\n", "utf-8")
    (builtin / ".editorconfig").write_text("root = true\n", "utf-8")  # non-jinja: copied verbatim
    out = tmp_path / "sdk"
    out.mkdir()
    written = scaffold.render_scaffold(builtin, None, out, _ctx())
    assert (out / "pyproject.toml").read_text() == "name = 'acme-sdk'\n"
    assert (out / ".github" / "workflows" / "ci.yml").exists()
    assert (out / ".editorconfig").read_text() == "root = true\n"
    assert "pyproject.toml" in written


def test_override_replaces_builtin(tmp_path: Path) -> None:
    builtin = tmp_path / "scaffold"
    builtin.mkdir()
    (builtin / "README.md.jinja").write_text("BUILTIN {{ package }}\n", "utf-8")
    overrides = tmp_path / "overrides"
    overrides.mkdir()
    (overrides / "README.md.jinja").write_text("OVERRIDE {{ package }}\n", "utf-8")
    out = tmp_path / "sdk"
    out.mkdir()
    scaffold.render_scaffold(builtin, overrides, out, _ctx())
    assert (out / "README.md").read_text() == "OVERRIDE acme\n"


def test_conditional_skip_via_jinja(tmp_path: Path) -> None:
    # A template that renders to empty/whitespace-only is skipped (used to gate
    # component tests on has_pagination etc.)
    builtin = tmp_path / "scaffold"
    builtin.mkdir()
    (builtin / "test_pagination.py.jinja").write_text(
        "{% if has_pagination %}import x{% endif %}", "utf-8"
    )
    out = tmp_path / "sdk"
    out.mkdir()
    written = scaffold.render_scaffold(builtin, None, out, _ctx(has_pagination=False))
    assert not (out / "test_pagination.py").exists()
    assert "test_pagination.py" not in written
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 pytest tests/test_scaffold.py -q`
Expected: FAIL — `ModuleNotFoundError: phantasos.scaffold`.

- [ ] **Step 3: Implement `src/phantasos/scaffold.py`**

```python
"""Render the project scaffold (built-in + per-product overrides) into an SDK."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

_BUILTIN = Path(__file__).parent / "scaffold"


def _collect(root: Path) -> dict[str, Path]:
    """Map relative-path -> absolute source for every file under root."""
    out: dict[str, Path] = {}
    if root and root.is_dir():
        for p in root.rglob("*"):
            if p.is_file():
                out[str(p.relative_to(root))] = p
    return out


def builtin_dir() -> Path:
    return _BUILTIN


def render_scaffold(
    builtin: Path, overrides: Path | None, out_dir: Path, context: dict[str, Any]
) -> list[str]:
    """Render built-in scaffold + overrides into out_dir. Overrides win by rel-path.

    `.jinja` templates are rendered (suffix stripped); other files are copied verbatim.
    A template that renders to only-whitespace is skipped (used to gate optional files).
    """
    files = _collect(builtin)
    files.update(_collect(overrides) if overrides else {})

    env = Environment(  # noqa: S701  renders config/source, not HTML
        loader=FileSystemLoader([str(p) for p in (builtin, overrides) if p]),
        keep_trailing_newline=True,
        autoescape=False,
    )
    written: list[str] = []
    for rel, src in sorted(files.items()):
        dest_rel = rel[: -len(".jinja")] if rel.endswith(".jinja") else rel
        dest = out_dir / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".jinja"):
            rendered = env.get_template(rel).render(**context)
            if not rendered.strip():
                continue  # gated-out optional file
            dest.write_text(rendered, encoding="utf-8")
        else:
            shutil.copyfile(src, dest)
        written.append(dest_rel)
    return written
```
NOTE on the env loader: both `builtin` and `overrides` are search paths; since the override
file has the same rel-path as the builtin, `FileSystemLoader` resolves the FIRST match — so
list `overrides` FIRST when present. Fix the loader to `[str(p) for p in (overrides, builtin) if p]`
so overrides shadow built-ins at template-resolution time too. (Update the code above to put
`overrides` first.)

- [ ] **Step 4: Run to verify they pass** (after the overrides-first loader fix)

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 pytest tests/test_scaffold.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/scaffold.py tests/test_scaffold.py
git commit -m "feat(scaffold): render built-in scaffold + per-product overrides into the SDK"
```

---

### Task 4: Wire scaffold + ignore into the build pipeline; package-data

**Files:** Modify `src/phantasos/__init__.py`, `pyproject.toml`; Test `tests/test_cli.py`.

- [ ] **Step 1: Write failing test** (append to `tests/test_cli.py`) — verify the build writes the ignore file before generate and runs the scaffold

```python
def test_build_writes_ignore_and_scaffolds(tmp_path, monkeypatch) -> None:
    import phantasos
    from phantasos.productconfig import load_product

    calls: list[str] = []

    def fake_generate(spec_path, out_dir, package, library="urllib3"):
        # the ignore file must already exist when generate runs
        assert (Path(out_dir) / ".openapi-generator-ignore").exists()
        calls.append("generate")
        pkg = Path(out_dir) / package
        (pkg / "api").mkdir(parents=True)
        (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr("phantasos.generate.generate", fake_generate)
    monkeypatch.setattr("phantasos.smoke.smoke", lambda *a, **k: {"skipped": True, "operations": 0})
    monkeypatch.setattr("phantasos.scaffold.render_scaffold", lambda *a, **k: calls.append("scaffold") or [])

    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out\nbase_url: b\nfacade: false\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, repo_url: https://x/y}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    phantasos.build(loaded, run_smoke=False)
    assert calls == ["generate", "scaffold"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -k ignore_and_scaffold -q`
Expected: FAIL — build does neither yet.

- [ ] **Step 3: Wire into `build()` in `__init__.py`**

(a) Before the `generate.generate(...)` call, add:
```python
    generate.write_openapi_generator_ignore(project_dir)
```
(b) After the `vendor` step (step 4) and before provenance, add a scaffold step:
```python
    # 4b. scaffold the project (built-in + per-product overrides, overwrite)
    from . import scaffold

    overrides = loaded.base_dir / "overrides"
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        overrides if overrides.is_dir() else None,
        project_dir,
        loaded.context,
    )
```
(Add `from . import scaffold` lazily as shown, consistent with the other lazy imports.)

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_cli.py -k ignore_and_scaffold -q`
Expected: PASS.

- [ ] **Step 5: Ship `scaffold/**` as package data** — in `pyproject.toml` `[tool.hatch.build.targets.wheel]`, extend `artifacts`:
```toml
artifacts = [
    "src/phantasos/components/**/*.jinja",
    "src/phantasos/scaffold/**",
]
```

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/__init__.py pyproject.toml tests/test_cli.py
git commit -m "feat(build): write OAG ignore before generate; run scaffold after vendor; ship scaffold data"
```

---

### Task 5: Smoke installs via `pip install <project_dir>`

**Files:** Modify `src/phantasos/smoke.py`; Test `tests/test_smoke.py`.

- [ ] **Step 1: Update the failing-condition + helper.** The fixture `_make_generated_pkg` in `tests/test_smoke.py` currently writes a `requirements.txt`. Change the smoke contract to require a `pyproject.toml` and install the project dir. First update the tests: in `_make_generated_pkg`, write a minimal installable `pyproject.toml` instead of (or in addition to) `requirements.txt`:
```python
    (project_dir / "pyproject.toml").write_text(
        f"[project]\nname = '{pkgname}'\nversion = '0'\nrequires-python = '>=3.9'\n"
        f"[build-system]\nrequires = ['hatchling']\nbuild-backend = 'hatchling.build'\n"
        f"[tool.hatch.build.targets.wheel]\npackages = ['{pkgname}']\n",
        encoding="utf-8",
    )
```
And update `test_ensure_smoke_venv_missing_requirements` → rename to `_missing_pyproject` and assert the SmokeError mentions `pyproject`.

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_smoke.py -q`
Expected: FAIL — `_ensure_smoke_venv` still checks `requirements.txt`.

- [ ] **Step 3: Update `_ensure_smoke_venv` in `smoke.py`** — install the project instead of a requirements file:
```python
def _ensure_smoke_venv(project_dir: Path) -> Path:
    """Create (or reuse) a cached venv with the SDK installed; return its python."""
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        raise SmokeError(
            f"no pyproject.toml in {project_dir}; cannot isolate the smoke check. "
            f"Pass --no-smoke to skip."
        )
    key = hashlib.sha256(pyproject.read_bytes()).hexdigest()[:16]
    venv_dir = provision.cache_dir() / "smoke-envs" / key
    py = _venv_python(venv_dir)
    ready = venv_dir / ".ready"
    if ready.exists() and py.exists():
        return py
    shutil.rmtree(venv_dir, ignore_errors=True)
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    subprocess.run(
        [str(py), "-m", "pip", "install", "-q", str(project_dir)],
        check=True,
        env=_sanitized_env(),
    )
    ready.write_text("")
    return py
```
NOTE: the import-walk's `sys.path.insert(0, project_dir)` is now redundant (the SDK is
installed in the venv) but harmless — leave it; it also lets the check work if the package is
importable from source. The cache key is now a hash of `pyproject.toml` (changes when deps change).

- [ ] **Step 4: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 pytest tests/test_smoke.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/smoke.py tests/test_smoke.py
git commit -m "feat(smoke): install the SDK via pip install <project_dir> (pyproject-based)"
```

---

### Task 6: Scaffold templates — core packaging (`pyproject`, `.gitignore`, `.editorconfig`, `LICENSE`)

**Files:** Create `src/phantasos/scaffold/{pyproject.toml.jinja,.gitignore.jinja,.editorconfig,LICENSE.jinja}`.

- [ ] **Step 1: Create `src/phantasos/scaffold/pyproject.toml.jinja`** (the critical one — SDK packaging with default/overridable deps; uses `project.*` flattened context):

```jinja
[project]
name = "{{ distribution }}"
version = "0.1.0"
description = "{{ description }}"
readme = "README.md"
requires-python = ">=3.11"
license = "{{ license }}"
authors = [{ name = "{{ author }}", email = "{{ author_email }}" }]
dependencies = [
{% for dep in dependencies %}    "{{ dep }}",
{% endfor %}]

[project.urls]
Repository = "{{ repo_url }}"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["{{ package }}"]

[dependency-groups]
test = ["pytest>=8", "pytest-cov>=5"]
lint = ["ruff>=0.6"]
typecheck = ["mypy>=1.11"]
dev = [{ include-group = "test" }, { include-group = "lint" }, { include-group = "typecheck" }, "nox>=2024.4", "pre-commit>=3.7"]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
# Generated code; keep the SDK lint pragmatic.
select = ["E", "F", "I", "UP", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create the other three** by adapting phantasos's own files:
  - `src/phantasos/scaffold/.gitignore.jinja` — copy phantasos's `.gitignore` (it's generic; no substitution needed, but keep the `.jinja` suffix for uniformity, or use a plain `.gitignore` — plain is fine since no vars). Use a plain `.gitignore` (non-jinja, copied verbatim) with standard Python ignores (`__pycache__/`, `*.pyc`, `.venv/`, `dist/`, `build/`, `*.egg-info/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage`).
  - `src/phantasos/scaffold/.editorconfig` — copy phantasos's `.editorconfig` verbatim (non-jinja).
  - `src/phantasos/scaffold/LICENSE.jinja` — the Apache-2.0 license text with `{{ author }}`/year in the copyright line. (Read phantasos's `LICENSE`; substitute the copyright holder line to use `{{ author }}` and year 2026. If `license` is not Apache-2.0 this needs adjusting, but Apache-2.0 is the default and only supported value for now — note this limitation.)

- [ ] **Step 3: Verify they render** with a quick unit check (append to `tests/test_scaffold.py`):
```python
def test_builtin_pyproject_renders(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "a@b.c", "repo_url": "https://x/y",
           "package": "acme", "dependencies": ["pydantic >= 2.11"]}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    pp = (out / "pyproject.toml").read_text()
    assert 'name = "acme-sdk"' in pp and "pydantic >= 2.11" in pp
    assert 'packages = ["acme"]' in pp
```
Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 pytest tests/test_scaffold.py -k pyproject_renders -q`
Expected: PASS. (This also confirms `.jinja` files render via the real built-in dir. The render will include whatever other scaffold files exist so far — that's fine.)

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/scaffold tests/test_scaffold.py
git commit -m "feat(scaffold): core packaging templates (pyproject, gitignore, editorconfig, LICENSE)"
```

---

### Task 7: Scaffold templates — `noxfile` + `.pre-commit-config`

**Files:** Create `src/phantasos/scaffold/{noxfile.py.jinja,.pre-commit-config.yaml.jinja}`.

- [ ] **Step 1: Create `noxfile.py.jinja`** — a slimmed SDK noxfile (lint + type-check + tests across `python_versions`). Adapt phantasos's `noxfile.py` but drop the docs/smoke/audit sessions (the SDK CI handles those via workflows). Use `{{ python_versions }}` for the test matrix:
```jinja
"""Task runner for {{ distribution }} (generated by phantasos)."""

from __future__ import annotations

import nox

nox.options.default_venv_backend = "uv"
PYTHON_VERSIONS = {{ python_versions }}


@nox.session
def lint(session: nox.Session) -> None:
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session
def type_check(session: nox.Session) -> None:
    session.install("mypy", ".")
    session.run("mypy", "{{ package }}")


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    session.install(".", "pytest", "pytest-cov")
    session.run("pytest", "--cov={{ package }}", *session.posargs)
```

- [ ] **Step 2: Create `.pre-commit-config.yaml.jinja`** — adapt phantasos's `.pre-commit-config.yaml`: keep `pre-commit-hooks` (hygiene), `ruff` (check+format), `gitleaks`; drop `mypy`/`codespell`/`uv-lock` to keep the SDK hook set lean. No `{{ }}` substitution needed, but keep `.jinja` for uniformity (or make it a plain file — plain is simpler since no vars; use plain `.pre-commit-config.yaml`).

- [ ] **Step 3: Verify render** — add a quick assertion to `tests/test_scaffold.py` that after rendering the built-in scaffold with a full context, `noxfile.py` exists and contains the package name. Run the scaffold test file. Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/scaffold tests/test_scaffold.py
git commit -m "feat(scaffold): noxfile + pre-commit templates"
```

---

### Task 8: Scaffold templates — CI/CD + security + docs workflows + mkdocs

**Files:** Create `src/phantasos/scaffold/.github/workflows/{ci,release,audit,secrets,codeql,docs}.yml.jinja` and `src/phantasos/scaffold/mkdocs.yml.jinja`.

Adapt phantasos's own workflows. Keep the **pinned action SHAs** from phantasos's current workflows (they're current/Node-24). Substitutions per file:

- [ ] **Step 1: `ci.yml.jinja`** — adapt phantasos `ci.yml`: jobs lint + type_check + tests matrix over `{{ python_versions }}`; **remove the smoke job** (that's phantasos-only). The SDK CI runs `uv run nox -s lint type_check tests-<ver>` (or `pytest`). Substitute the python matrix with `{{ python_versions }}`. (The SDK has no Java/OAG, so no setup-java/cache.)

- [ ] **Step 2: `release.yml.jinja`** — adapt phantasos `release.yml`: PyPI **trusted publishing** on tag push, building the wheel/sdist. Substitute nothing spec-specific (it's generic), but ensure the build job builds `{{ distribution }}`. Keep the pinned `pypa/gh-action-pypi-publish` SHA from phantasos.

- [ ] **Step 3: `audit.yml.jinja`, `secrets.yml.jinja`, `codeql.yml.jinja`** — copy phantasos's `audit.yml` (pip-audit), `secrets.yml` (gitleaks — keep the pinned `gitleaks-action` SHA + `pull-requests: read` permission we added), and `codeql.yml` (keep the `contents/actions/packages/security-events` permissions fix). These are generic; minimal/no substitution. For codeql `languages: python` stays.

- [ ] **Step 4: `docs.yml.jinja` + `mkdocs.yml.jinja`** — adapt phantasos's `docs.yml` (build + Pages deploy) and `mkdocs.yml`. Substitute `site_name`, `repo_url`, `repo_name` with `{{ distribution }}`/`{{ repo_url }}`. The SDK mkdocs can be minimal (mkdocstrings over `{{ package }}`).

- [ ] **Step 5: Verify** — add a `tests/test_scaffold.py` assertion that all 6 workflow files + mkdocs render and are valid YAML after rendering with a full context:
```python
def test_builtin_workflows_render_valid_yaml(tmp_path: Path) -> None:
    import yaml

    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "a@b.c", "repo_url": "https://x/y",
           "package": "acme", "dependencies": ["pydantic"], "python_versions": ["3.12"],
           "has_auth": True, "has_pagination": True, "has_errors": True, "has_facade": True}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    for wf in (out / ".github" / "workflows").glob("*.yml"):
        yaml.safe_load(wf.read_text())  # raises on invalid YAML
    yaml.safe_load((out / "mkdocs.yml").read_text())
```
Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 pytest tests/test_scaffold.py -k workflows_render -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/scaffold tests/test_scaffold.py
git commit -m "feat(scaffold): CI/release/audit/secrets/codeql/docs workflows + mkdocs templates"
```

---

### Task 9: Scaffold meta files (`CHANGELOG`, `CONTRIBUTING`, `SECURITY`)

**Files:** Create `src/phantasos/scaffold/{CHANGELOG.md.jinja,CONTRIBUTING.md.jinja,SECURITY.md.jinja}`.

- [ ] **Step 1: Create the three** by adapting phantasos's versions, substituting the project name/repo where they appear: `CHANGELOG.md.jinja` (a Keep-a-Changelog stub for `{{ distribution }}` v0.1.0), `CONTRIBUTING.md.jinja` (dev setup: `uv sync`, `uv run nox`), `SECURITY.md.jinja` (report to `{{ author_email }}`).

- [ ] **Step 2: Verify** — add an assertion to `tests/test_scaffold.py` that the rendered SDK contains `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` and that `SECURITY.md` contains `{{ author_email }}`'s value. Run the file. Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/phantasos/scaffold tests/test_scaffold.py
git commit -m "feat(scaffold): CHANGELOG/CONTRIBUTING/SECURITY templates"
```

---

### Task 10: Built-in component behavioral tests

**Files:** Create `src/phantasos/scaffold/tests/{conftest.py.jinja,test_auth.py.jinja,test_pagination.py.jinja,test_errors.py.jinja,test_facade.py.jinja,test_lenient_enums.py.jinja}`.

These reconstruct the lost component behavioral tests, **generalized + gated**. Each is wrapped so it renders to empty (and is skipped) when its component is absent.

- [ ] **Step 1: `conftest.py.jinja`** — puts the package on `sys.path` (mirror the old prisma-browser-sdk conftest):
```jinja
"""Pytest config for the {{ package }} SDK (generated)."""

import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get("SDK_UNDER_TEST", str(ROOT)))
warnings.simplefilter("ignore")  # lenient-enum warnings are expected
```

- [ ] **Step 2: The gated component tests.** Each file is `{% if has_<x> %}…{% endif %}` so it renders empty (skipped) when absent. They import from `{{ package }}.extras.*` (the vendored components). Author each to exercise the vendored component's public behavior:
  - `test_auth.py.jinja` (`has_auth`): import `{{ package }}.extras.auth`, assert `api_client_from_env` / `api_client_from_credentials` exist and the config class `{{ config_class_name }}` is importable.
  - `test_pagination.py.jinja` (`has_pagination`): import `{{ package }}.extras.pagination`, assert `paginate` exists and is callable.
  - `test_errors.py.jinja` (`has_errors`): import `{{ package }}.extras.errors`, assert the error-extraction helper exists.
  - `test_facade.py.jinja` (`has_facade`): import `{{ package }}.extras.facade`, assert the client class binds at least one resource attribute.
  - `test_lenient_enums.py.jinja`: a generic test that an unknown enum value passes through with a warning — gated on whether lenient-enum patches apply (use `{% if has_facade or has_auth %}` as a proxy, or always-on since lenient enums are a generic patch; render always but keep it robust to no-enums by skipping at runtime if no enum module is found).

  Keep each test SMALL and robust (import-level + a single behavioral assertion). They must pass against a real generated SDK (Task 13 verifies). Read the vendored component templates (`src/phantasos/components/*`) to use the correct public names.

- [ ] **Step 3: Verify gating** — a `tests/test_scaffold.py` test that with `has_pagination=False` the rendered SDK has no `tests/test_pagination.py`, and with all `has_*` true it has all of them. Run. Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/phantasos/scaffold/tests tests/test_scaffold.py
git commit -m "feat(scaffold): built-in gated component behavioral tests"
```

---

### Task 11: Migrate the two example products (project block + overrides)

**Files:** Modify `products/{adem,prisma-browser}/sdk.yml`; Create `products/{adem,prisma-browser}/overrides/README.md.jinja` (+ prisma `overrides/tests/test_models.py.jinja`).

- [ ] **Step 1: Add `project:` to `products/prisma-browser/sdk.yml`**:
```yaml
project:
  distribution: prisma-browser-sdk
  description: Python SDK for the Palo Alto Networks Prisma Browser Management APIs
  author: Oliver Kaiser
  author_email: oliver.kaiser@outlook.com
  repo_url: https://github.com/kaisero/prisma-browser-sdk
```

- [ ] **Step 2: Add `project:` to `products/adem/sdk.yml`**:
```yaml
project:
  distribution: adem-sdk
  description: Python SDK for the Palo Alto Networks ADEM data API
  author: Oliver Kaiser
  author_email: oliver.kaiser@outlook.com
  repo_url: https://github.com/kaisero/adem-sdk
```

- [ ] **Step 3: Create `products/prisma-browser/overrides/README.md.jinja`** and `products/adem/overrides/README.md.jinja` — a per-product README template (title `{{ distribution }}`, install `pip install {{ distribution }}`, a usage snippet referencing `{{ package }}`, link to `{{ repo_url }}`).

- [ ] **Step 4: Create `products/prisma-browser/overrides/tests/test_models.py.jinja`** — the `User.from_dict`/`to_dict` round-trip + unknown-enum-tolerance test (reconstruct from the design's example; import `{{ package }}.models.user`). adem may omit per-product tests.

- [ ] **Step 5: Verify both load** (no build yet):
```bash
PYTHONPATH=src uv run --no-project --python 3.12 --with pydantic --with ruamel.yaml \
  python -c "from phantasos.productconfig import load_product; [print(load_product(p).config.project.distribution) for p in ('products/prisma-browser/sdk.yml','products/adem/sdk.yml')]"
```
Expected: `prisma-browser-sdk` and `adem-sdk`.

- [ ] **Step 6: Commit**

```bash
git add products
git commit -m "feat(products): add project block + overrides (README, prisma tests) to examples"
```

---

### Task 12: Onboarding doc + README/AUTHORING updates

**Files:** Create `docs/ONBOARDING.md`; Modify `README.md`, `docs/AUTHORING_A_SPEC.md`.

- [ ] **Step 1: Create `docs/ONBOARDING.md`** documenting the new-SDK flow: create `products/<name>/{openapi.yml,sdk.yml,overrides/README.md.jinja}`; the `project:` block; that scaffold default deps usually suffice; the "generate once → read OAG `requirements.txt` → set `project.dependencies` if different" recipe; that a one-off smoke failure from a missing dep is acceptable; and that everything in the SDK is generated (never hand-edit it).

- [ ] **Step 2: Update `docs/AUTHORING_A_SPEC.md`** — add a `project:` block section + an `overrides/` section (README required, optional tests) to the existing sdk.yml docs.

- [ ] **Step 3: Update `README.md`** — note that generated SDKs are full phantasos-grade projects (pyproject, CI/CD, tests) scaffolded from `src/phantasos/scaffold/` + `products/<product>/overrides/`.

- [ ] **Step 4: Commit**

```bash
git add docs/ONBOARDING.md docs/AUTHORING_A_SPEC.md README.md
git commit -m "docs: ONBOARDING guide; document project block, overrides, scaffold"
```

---

### Task 13: Lint/type-check + full e2e verification (the real proof)

**Files:** none (verification + any fixes).

- [ ] **Step 1: Lint + mypy + unit suite**

Run:
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s lint type_check
PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with pydantic --with ruamel.yaml --with jinja2 --with urllib3 --with python-dateutil --with typing_extensions pytest tests/ -q -p no:cacheprovider
```
Expected: lint + mypy clean; all unit tests pass. Fix any issues in the new code.

- [ ] **Step 2: Build both SDKs end-to-end**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s smoke`
Expected: both build with 0 smoke failures (smoke now `pip install`s the scaffolded pyproject).

- [ ] **Step 3: Confirm the SDK is phantasos-grade and junk-free**

Run:
```bash
cd /home/ubuntu/git/prisma-browser-sdk
echo "should EXIST:"; ls pyproject.toml noxfile.py .pre-commit-config.yaml mkdocs.yml CHANGELOG.md .github/workflows/{ci,release,audit,secrets,codeql,docs}.yml tests/ README.md 2>&1
echo "should be GONE:"; ls setup.py setup.cfg requirements.txt tox.ini git_push.sh .gitlab-ci.yml .travis.yml .github/workflows/python.yml 2>&1
echo "tests present (gated component + per-product model):"; ls tests/
cd -
```
Expected: the scaffold files exist; the OAG junk is gone; `tests/` has the component tests (auth/pagination/errors/facade present for prisma — it vendors all four) + `test_models.py`.

- [ ] **Step 4: Run the regenerated SDK's own test suite (the behavioral guardrail — now version-controlled)**

Run:
```bash
cd /home/ubuntu/git/prisma-browser-sdk
uv run --no-project --python 3.12 --with pytest --with-requirements <(echo "urllib3
python-dateutil
pydantic
typing-extensions") pytest tests/ -q -p no:cacheprovider
cd -
```
Expected: the scaffolded component tests + the per-product model test pass against the regenerated SDK. (This is the guardrail that can never be lost again — the tests are version-controlled in phantasos.)

- [ ] **Step 5: Final review against the design**

Re-read `docs/specs/2026-06-08-sdk-project-scaffold-design.md`; confirm each section maps to merged work. If green, Phase C is complete.

---

## Notes for the executor

- **Templates are adaptations of phantasos's own infra.** For each workflow/nox/pre-commit/meta template, READ phantasos's corresponding file and substitute the listed `{{ project.* }}`/`{{ package }}` values; keep phantasos's pinned action SHAs (they're current). Do NOT invent new CI structure — mirror phantasos's, minus the generator-only bits (Java/OAG/smoke).
- **Overrides shadow built-ins at BOTH file-collection and template-resolution.** The Jinja `FileSystemLoader` must list `overrides` before `builtin` (Task 3 note).
- **Empty render = skip.** Gated component tests render to whitespace when their component is absent and are skipped — that's the gating mechanism (Task 3 / Task 10).
- **Component tests must use the real vendored public names** — read `src/phantasos/components/*.jinja` to get the actual function/class names (`api_client_from_env`, `paginate`, the facade client, `{{ config_class_name }}`).
- **Filesystem note (sandbox):** use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for `uv run`/nox; smoke venvs live under `~/.cache/phantasos` (home fs).
- **Branch:** stacked on `declarative-products-config`. The smoke change (Task 5) modifies the isolated-smoke code from the previous phase — that's expected.
