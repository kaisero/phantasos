# CLI Generator — Phase 3g: Full project scaffolding via `render_scaffold` reuse — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `phantasos cli build` emit a full phantasos-grade project (README, pyproject with the **correct SDK distribution dependency** + console-script, noxfile, CI/CD, pre-commit, `.env.example`, mkdocs, …) by **reusing the existing SDK scaffold system** (`src/phantasos/scaffold.py` + `src/phantasos/scaffold/`), instead of the lean ad-hoc pyproject Phase 2b emitted.

**Architecture:** `cli build` builds a CLI-shaped scaffold **context** (distribution, package, deps `[typer, rich, pyyaml, <sdk-distribution>]`, a `scripts` entry, component flags off) and calls the same `scaffold.render_scaffold(builtin_dir, cli_overrides, out_dir, context)` the SDK uses. `render_scaffold` overwrites only its template set, leaving the `render_cli`-owned `_generated/` and the hand-owned `main.py`/`custom/`/`hooks.py` untouched. `pyproject.toml` moves from `render_cli` (emit-once) to **scaffold-owned (overwrite)**, matching the SDK's "pure artifact, never hand-edit" model.

**Tech Stack:** Python 3.11–3.14, Jinja2 (`StrictUndefined`), Pydantic v2, pytest. Test runner: `uv run`.

**Spec:** `docs/superpowers/specs/2026-06-09-cli-generator-design.md` + the SDK scaffold design `docs/superpowers/specs/2026-06-08-sdk-project-scaffold-design.md`. **Roadmap:** `…phase-3-roadmap.md` §3g. **Builds on:** Phases 1/2a/2b on branch `cli-generator`.

---

## Conventions (every task)
- Env: `export UV_PROJECT_ENVIRONMENT=/tmp/phantasos-venv` then `uv run …` (repo `.venv` can't hold symlinks).
- Repo root `/home/ubuntu/git/phantasos`, branch `cli-generator`. **Do NOT `git checkout`/`switch`/`reset`** — commit on the branch; `git show <sha>:<path>` for history.
- TDD; new test imports at the TOP of files; run `ruff check src/phantasos tests/` AND `mypy src/phantasos/generator src/phantasos/cli.py` before each commit (both clean, mypy strict).
- Fake SDK fixture: `tests/fixtures/fakesdk/`. Real SDK: `/home/ubuntu/git/prisma-browser-sdk` (product `products/prisma-browser/` has a `project:` block with `distribution: prisma-browser-sdk`).

## Key facts this plan relies on (verified)
- `scaffold.render_scaffold(builtin, overrides, out_dir, context)` renders `builtin`+`overrides` (overrides win by rel-path), strips `.jinja`, **skips templates that render to only-whitespace**, and **only writes its own template set** (it does not delete/clobber files outside it). Uses `StrictUndefined` — every variable a template references MUST be in `context`.
- Builtin scaffold tree (`src/phantasos/scaffold/`): `pyproject.toml.jinja`, `noxfile.py.jinja`, `mkdocs.yml.jinja`, `CHANGELOG/CONTRIBUTING/SECURITY.md.jinja`, `LICENSE.jinja`, `.editorconfig`, `.gitignore`, `.pre-commit-config.yaml`, `.github/workflows/{ci,release,audit,secrets,codeql,docs}.yml.jinja`, `tests/{conftest,test_auth,test_pagination,test_errors,test_facade}.py.jinja`. There is **no README** in the builtin — overrides must supply it.
- The SDK component tests gate on `{% if has_auth %}` etc.; with those flags **False** they render empty → skipped. `pyproject.toml.jinja` is fully context-driven (`distribution`, `description`, `dependencies` loop, `package`, `repo_url`, `author`, `license`) and currently has **no** `[project.scripts]`.
- `loaded.context` (built in `productconfig.load_product`) already contains: `package, library, base_url, spec_version, spec_title, has_auth, has_pagination, has_errors, has_facade, config_class_name` and (when `project:` present) `distribution, description, author, author_email, repo_url, license, python_versions, dependencies`. **Reuse it as the base for the CLI context** so every scaffold variable is satisfied.

---

## File structure (this phase)
- Modify: `src/phantasos/scaffold/pyproject.toml.jinja` — add a conditional `[project.scripts]` block.
- Create: `src/phantasos/scaffold/.env.example.jinja` — guarded auth-vars template (no-op unless `auth_env_vars` provided → SDK build unaffected).
- Modify: `src/phantasos/generator/cli/cliconfig.py` — `CliConfig.project: ProjectConfig | None`.
- Create: `src/phantasos/generator/cli/scaffold_context.py` — `build_cli_scaffold_context(loaded, ir, cli_cfg) -> dict`.
- Create: `src/phantasos/generator/cli/cli_overrides/README.md.jinja` — generic CLI README (the required README override).
- Modify: `src/phantasos/generator/cli/render_cli.py` — **remove** pyproject emission (scaffold owns it now).
- Modify: `src/phantasos/cli.py` — `cli build` calls `render_scaffold` with the CLI context + overrides.
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md` — note pyproject is scaffold-owned.
- Tests: `tests/test_cli_scaffold.py` (context builder + scaffold integration), extend `tests/test_cli_command.py` (real wiring), `tests/test_scaffold.py` if it exists for the pyproject change.

---

## Task 1: `pyproject.toml.jinja` — conditional `[project.scripts]`

**Files:**
- Modify: `src/phantasos/scaffold/pyproject.toml.jinja`
- Test: `tests/test_cli_scaffold.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_scaffold.py
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

SCAFFOLD = Path("src/phantasos/scaffold")


def _render(template: str, ctx: dict) -> str:
    env = Environment(
        loader=FileSystemLoader(str(SCAFFOLD)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
    )
    return env.get_template(template).render(**ctx)


_BASE = dict(
    distribution="x", description="d", license="Apache-2.0", author="a",
    author_email="a@b.c", repo_url="https://x", package="x",
    dependencies=["typer>=0.12"],
)


def test_pyproject_emits_scripts_when_provided():
    out = _render("pyproject.toml.jinja", {**_BASE, "scripts": {"x-cli": "x.main:app"}})
    assert "[project.scripts]" in out
    assert 'x-cli = "x.main:app"' in out


def test_pyproject_no_scripts_block_for_sdk():
    # SDK context has no `scripts` key — StrictUndefined must not error, no scripts block
    out = _render("pyproject.toml.jinja", _BASE)
    assert "[project.scripts]" not in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli_scaffold.py -k pyproject -v`
Expected: FAIL — `test_pyproject_emits_scripts_when_provided` (no scripts block emitted).

- [ ] **Step 3: Implement** — in `src/phantasos/scaffold/pyproject.toml.jinja`, add this block right after the `[project.urls]` block (use `is defined` so the SDK's script-less context does not trip `StrictUndefined`):

```jinja
{% if scripts is defined and scripts %}
[project.scripts]
{% for name, target in scripts.items() %}{{ name }} = "{{ target }}"
{% endfor %}
{% endif %}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli_scaffold.py -k pyproject -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Confirm the SDK build is unaffected + commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/`
Expected: all green (the SDK never passes `scripts`, so its pyproject is byte-identical).
```bash
git add src/phantasos/scaffold/pyproject.toml.jinja tests/test_cli_scaffold.py
git commit -m "feat(scaffold): conditional [project.scripts] in pyproject (CLI console-script)"
```

---

## Task 2: `.env.example.jinja` (guarded; auth env vars)

**Files:**
- Create: `src/phantasos/scaffold/.env.example.jinja`
- Test: `tests/test_cli_scaffold.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_env_example_renders_vars_when_provided():
    out = _render(".env.example.jinja", {"auth_env_vars": [
        {"name": "PRISMA_CLIENT_ID", "example": "<client-id>"},
        {"name": "SCOPE", "example": "tsg_id:123"},
    ]})
    assert "PRISMA_CLIENT_ID=<client-id>" in out
    assert "SCOPE=tsg_id:123" in out


def test_env_example_empty_without_vars():
    # SDK context has no auth_env_vars -> renders only-whitespace -> render_scaffold skips it
    out = _render(".env.example.jinja", {})
    assert out.strip() == ""
```

- [ ] **Step 2: Run → FAIL** (`uv run pytest tests/test_cli_scaffold.py -k env_example -v`) — template missing.

- [ ] **Step 3: Create `src/phantasos/scaffold/.env.example.jinja`**

```jinja
{% if auth_env_vars is defined and auth_env_vars %}# Credentials for this CLI (loaded by the SDK's Client.from_env()).
# Copy to .env and fill in real values.
{% for v in auth_env_vars %}{{ v.name }}={{ v.example }}
{% endfor %}{% endif %}
```

- [ ] **Step 4: Run → PASS** (`uv run pytest tests/test_cli_scaffold.py -k env_example -v`, 2 passed).

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/`
(The SDK build renders `.env.example.jinja` to whitespace — `render_scaffold` skips it — so the SDK is unaffected. Confirm `tests/` green.)
```bash
git add src/phantasos/scaffold/.env.example.jinja tests/test_cli_scaffold.py
git commit -m "feat(scaffold): guarded .env.example template (auth env vars)"
```

---

## Task 3: `CliConfig.project` block

**Files:**
- Modify: `src/phantasos/generator/cli/cliconfig.py`
- Test: `tests/test_cli_config.py`

- [ ] **Step 1: Write the failing test** (append; imports at top)

```python
def test_cli_config_optional_project_block(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text(
        "project:\n"
        "  distribution: prisma-browser-cli\n"
        "  author: Oliver Kaiser\n"
        "  author_email: o@example.com\n"
        "  repo_url: https://github.com/x/prisma-browser-cli\n"
        "  description: CLI for the Prisma Browser SDK\n"
    )
    cfg = load_cli_config(p)
    assert cfg.project is not None
    assert cfg.project.distribution == "prisma-browser-cli"


def test_cli_config_project_absent_is_none(tmp_path):
    p = tmp_path / "cli.yml"
    p.write_text("hide: []\n")
    assert load_cli_config(p).project is None
```

- [ ] **Step 2: Run → FAIL** (`CliConfig` has no `project`).

- [ ] **Step 3: Implement** — in `cliconfig.py`, reuse the SDK's `ProjectConfig`:

```python
from ...productconfig import ProjectConfig  # adjust relative depth: phantasos.productconfig
```
(Concretely: `cliconfig.py` is at `phantasos/generator/cli/cliconfig.py`; `ProjectConfig` is at `phantasos/productconfig.py`, so the import is `from ...productconfig import ProjectConfig`.)
Add to `CliConfig`:
```python
    project: ProjectConfig | None = None
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Lint, type-check, commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator/cli/cliconfig.py`
```bash
git add src/phantasos/generator/cli/cliconfig.py tests/test_cli_config.py
git commit -m "feat(cli-gen): optional cli.yml project block (ProjectConfig)"
```

---

## Task 4: `build_cli_scaffold_context`

The heart of the combine: build the scaffold context for the CLI from the SDK product's context.

**Files:**
- Create: `src/phantasos/generator/cli/scaffold_context.py`
- Test: `tests/test_cli_scaffold.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from phantasos.generator.cli.scaffold_context import build_cli_scaffold_context


class _FakeLoaded:
    """Minimal stand-in for LoadedProduct (only what the builder reads)."""

    def __init__(self):
        self.context = {
            "package": "prisma_browser", "library": "urllib3",
            "base_url": "https://api", "spec_version": "1.0.0",
            "spec_title": "Prisma Browser", "has_auth": True,
            "has_pagination": True, "has_errors": True, "has_facade": True,
            "config_class_name": "PrismaSaseConfiguration",
            "distribution": "prisma-browser-sdk", "description": "Python SDK",
            "author": "Oliver", "author_email": "o@x.com",
            "repo_url": "https://github.com/x/prisma-browser-sdk",
            "license": "Apache-2.0", "python_versions": ["3.11", "3.12"],
            "dependencies": ["httpx", "urllib3", "pydantic"],
        }
        self.auth = type("A", (), {"scope_env": "SCOPE",
                                   "base_url_env": "PRISMA_SASE_BASE_URL"})()


def test_build_context_overrides_for_cli():
    ctx = build_cli_scaffold_context(_FakeLoaded(), ir=None, cli_cfg=None)
    # package + distribution become the CLI's
    assert ctx["package"] == "prisma_browser_cli"
    assert ctx["distribution"] == "prisma-browser-cli"
    # SDK dep uses the SDK DISTRIBUTION name (not the import package)
    assert "prisma-browser-sdk" in ctx["dependencies"]
    assert "typer>=0.12" in ctx["dependencies"] and "rich>=13" in ctx["dependencies"]
    assert "prisma_browser" not in ctx["dependencies"]  # never the import name
    # console-script entry
    assert ctx["scripts"] == {"prisma-browser-cli": "prisma_browser_cli.main:app"}
    # component flags OFF so SDK component tests skip for the CLI
    assert ctx["has_auth"] is False and ctx["has_facade"] is False
    # description reflects the CLI
    assert "CLI" in ctx["description"]
    # auth env vars derived for .env.example
    names = {v["name"] for v in ctx["auth_env_vars"]}
    assert "SCOPE" in names and "PRISMA_SASE_BASE_URL" in names


def test_build_context_respects_cli_project_block():
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.productconfig import ProjectConfig

    cli_cfg = CliConfig(project=ProjectConfig(
        distribution="custom-cli", author="A", author_email="a@x",
        repo_url="https://x", description="My CLI"))
    ctx = build_cli_scaffold_context(_FakeLoaded(), ir=None, cli_cfg=cli_cfg)
    assert ctx["distribution"] == "custom-cli"
    assert ctx["description"] == "My CLI"
```

- [ ] **Step 2: Run → FAIL** (module missing).

- [ ] **Step 3: Implement `src/phantasos/generator/cli/scaffold_context.py`**

```python
"""Build the scaffold context for an emitted CLI project (reuses the SDK scaffold)."""

from __future__ import annotations

from typing import Any

_CLI_DEPS = ["typer>=0.12", "rich>=13", "pyyaml>=6"]


def _auth_env_vars(loaded: Any) -> list[dict[str, str]]:
    """Best-effort list of {name, example} from the SDK auth component for .env.example."""
    auth = getattr(loaded, "auth", None)
    out: list[dict[str, str]] = [
        {"name": "CLIENT_ID", "example": "<client-id>"},
        {"name": "CLIENT_SECRET", "example": "<client-secret>"},
    ]
    scope = getattr(auth, "scope_env", None)
    if scope:
        out.append({"name": str(scope), "example": "<scope>"})
    base = getattr(auth, "base_url_env", None)
    if base:
        out.append({"name": str(base), "example": "<base-url>"})
    return out


def build_cli_scaffold_context(loaded: Any, ir: Any, cli_cfg: Any) -> dict[str, Any]:
    """CLI scaffold context = the SDK product context, overridden for the CLI.

    Starting from `loaded.context` guarantees every scaffold variable is present
    (StrictUndefined). We then override the CLI-specific keys.
    """
    base = dict(loaded.context)
    sdk_distribution = base.get("distribution") or f"{base['package'].replace('_', '-')}-sdk"
    cli_package = f"{base['package']}_cli"
    cli_distribution = f"{sdk_distribution}-cli".replace("-sdk-cli", "-cli")

    project = getattr(cli_cfg, "project", None) if cli_cfg is not None else None

    ctx = dict(base)
    ctx.update(
        package=cli_package,
        distribution=(project.distribution if project else cli_distribution),
        description=(project.description if project and project.description
                     else f"CLI for {base.get('spec_title') or base['package']}"),
        dependencies=[*_CLI_DEPS, sdk_distribution],
        scripts={(project.distribution if project else cli_distribution):
                 f"{cli_package}.main:app"},
        # turn OFF SDK component tests for the CLI (they gate on these flags)
        has_auth=False, has_pagination=False, has_errors=False, has_facade=False,
        auth_env_vars=_auth_env_vars(loaded),
    )
    if project is not None:
        ctx.update(
            author=project.author, author_email=project.author_email,
            repo_url=project.repo_url, license=project.license,
            python_versions=project.python_versions,
        )
    return ctx
```

Note the `cli_distribution` computation: `prisma-browser-sdk` → `prisma-browser-cli` (the `.replace("-sdk-cli", "-cli")` collapses the doubled suffix). For a distribution not ending in `-sdk`, it appends `-cli`. (If the implementer finds a cleaner derivation, keep the test assertions as the contract.)

- [ ] **Step 4: Run → PASS** (`uv run pytest tests/test_cli_scaffold.py -k context -v`).

- [ ] **Step 5: Lint, type-check, commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos/generator tests/ && uv run mypy src/phantasos/generator`
```bash
git add src/phantasos/generator/cli/scaffold_context.py tests/test_cli_scaffold.py
git commit -m "feat(cli-gen): build CLI scaffold context (SDK-distribution dep, console-script, flags off)"
```

---

## Task 5: Generic CLI README override

`render_scaffold`'s builtin has no README; the CLI must supply one as an override (mirrors the SDK requiring `overrides/README.md.jinja`).

**Files:**
- Create: `src/phantasos/generator/cli/cli_overrides/README.md.jinja`
- Test: `tests/test_cli_scaffold.py`

- [ ] **Step 1: Write the failing test** (append)

```python
from phantasos.generator.cli.render_cli import cli_overrides_dir  # added in Step 3


def test_cli_overrides_has_readme():
    d = cli_overrides_dir()
    assert (d / "README.md.jinja").is_file()
    text = (d / "README.md.jinja").read_text()
    assert "{{ distribution }}" in text  # README is value-substituted
```

- [ ] **Step 2: Run → FAIL** (`cli_overrides_dir` missing / no README).

- [ ] **Step 3: Implement**
Create `src/phantasos/generator/cli/cli_overrides/README.md.jinja`:
```jinja
# {{ distribution }}

{{ description }}

A generated command-line interface over the `{{ spec_title }}` API. Verbs: `set` (create/patch/update),
`del`, `show`. Run `{{ distribution }} --help` to explore.

## Install
```bash
pip install -e .
```

## Configure
Copy `.env.example` to `.env` and fill in your credentials (loaded by the SDK at runtime).

## Usage
```bash
{{ distribution }} show --help
{{ distribution }} set <object> --help
```

> Generated by phantasos. The `_generated/` package is rebuilt on every `phantasos cli build`;
> hand-written commands/overrides live in `main.py`, `custom/`, and `hooks.py`.
```
Add a helper to `render_cli.py` (near `_TEMPLATES`):
```python
def cli_overrides_dir() -> Path:
    return Path(__file__).parent / "cli_overrides"
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos/generator tests/`
```bash
git add src/phantasos/generator/cli/cli_overrides/README.md.jinja src/phantasos/generator/cli/render_cli.py tests/test_cli_scaffold.py
git commit -m "feat(cli-gen): generic CLI README override for the scaffold"
```

---

## Task 6: Wire scaffold into `cli build`; remove pyproject from `render_cli`

**Files:**
- Modify: `src/phantasos/generator/cli/render_cli.py` (remove pyproject emission + its params)
- Modify: `src/phantasos/cli.py` (`cli build` calls `render_scaffold`)
- Test: `tests/test_cli_command.py`, `tests/test_cli_render.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli_command.py`)

```python
def test_cli_build_emits_full_project(tmp_path, monkeypatch):
    import phantasos.cli as climod

    sdk_ctx = {
        "package": "fakesdk", "library": "urllib3", "base_url": "http://x",
        "spec_version": "9.9.9", "spec_title": "FakeSDK",
        "has_auth": True, "has_pagination": False, "has_errors": False,
        "has_facade": True, "config_class_name": "Cfg",
        "distribution": "fakesdk-sdk", "description": "Fake SDK",
        "author": "A", "author_email": "a@x", "repo_url": "https://x",
        "license": "Apache-2.0", "python_versions": ["3.11", "3.12"],
        "dependencies": ["urllib3"],
    }

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-sdk"
        context = sdk_ctx
        auth = type("A", (), {"scope_env": "SCOPE", "base_url_env": "FAKE_BASE_URL"})()

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "build", "fakesdk"])
    assert rc == 0
    root = tmp_path / "fakesdk-cli"
    # package code (render_cli)
    assert (root / "fakesdk_cli" / "_generated" / "app.py").exists()
    assert (root / "fakesdk_cli" / "main.py").exists()
    # project shell (render_scaffold)
    assert (root / "README.md").exists()
    assert (root / "noxfile.py").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    assert (root / ".env.example").exists()
    pyproject = (root / "pyproject.toml").read_text()
    assert "fakesdk-sdk" in pyproject              # SDK distribution dep (the fix)
    assert "fakesdk_cli.main:app" in pyproject      # console-script
    assert "typer" in pyproject
    # SDK component tests did NOT render for the CLI (has_auth was forced False)
    assert not (root / "tests" / "test_auth.py").exists()
```

- [ ] **Step 2: Run → FAIL** (no scaffold emitted; pyproject from render_cli has wrong dep).

- [ ] **Step 3: Remove pyproject emission from `render_cli`**
In `src/phantasos/generator/cli/render_cli.py`: delete the `pyproject.toml.jinja` template render + the `distribution`/`sdk_dependency` params and the `pyproject.toml` emit-once block (scaffold owns pyproject now). Keep `_generated/` emission + hand-owned `main.py`/`hooks.py`/`custom/`. Delete `src/phantasos/generator/cli/templates/pyproject.toml.jinja`. Update/remove the Phase-2b tests that asserted render_cli emits pyproject (`tests/test_cli_render.py::test_emits_pyproject_with_console_script` / `test_pyproject_is_emit_once`) — those behaviors move to the scaffold; replace them with a note or delete (the scaffold tests + Task-6 integration test now cover pyproject). Do NOT leave a dangling reference to the removed params.

- [ ] **Step 4: Wire the scaffold call in `cli build`** (`src/phantasos/cli.py`, the `args.cli_cmd == "build"` branch). After `render_cli(...)`, add:
```python
        from . import scaffold
        from .generator.cli.render_cli import cli_overrides_dir
        from .generator.cli.scaffold_context import build_cli_scaffold_context

        scaffold_ctx = build_cli_scaffold_context(loaded, ir, cfg)
        scaffold.render_scaffold(
            scaffold.builtin_dir(), cli_overrides_dir(), out_dir, scaffold_ctx
        )
```
(`out_dir`, `loaded`, `ir`, `cfg` already exist in that branch from Phase 2b. `render_cli(...)` is still called for the package; just drop its `distribution`/`sdk_dependency` kwargs if you passed any.)

- [ ] **Step 5: Run → PASS**

Run: `uv run pytest tests/test_cli_command.py -v`
Expected: the new test passes; existing `cli discover`/`build` tests still pass (update the old `test_cli_build_emits_project` if it asserted the old lean pyproject — align it to the scaffold-emitted project or fold it into the new test).

- [ ] **Step 6: Full suite + lint + types + commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/ && uv run mypy src/phantasos/generator src/phantasos/cli.py`
```bash
git add src/phantasos/generator/cli/render_cli.py src/phantasos/cli.py tests/test_cli_command.py tests/test_cli_render.py
git rm src/phantasos/generator/cli/templates/pyproject.toml.jinja
git commit -m "feat(cli-gen): cli build emits full project via render_scaffold; pyproject is scaffold-owned"
```

---

## Task 7: Real-SDK build — full project for `prisma-browser`

**Files:**
- Test: `tests/test_cli_emitted_real.py` (append, gated)

- [ ] **Step 1: Write the gated test**

```python
def test_real_cli_build_emits_full_project(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    import phantasos.cli as climod
    from phantasos.cli import main

    # build into an isolated tmp dir (don't write to the real sibling)
    loaded = climod.load_product("prisma-browser")
    monkeypatch.setattr(type(loaded), "output_dir",
                        property(lambda self: tmp_path / "prisma-browser-sdk"), raising=False)
    # simplest: monkeypatch load_product to return `loaded` with output_dir redirected
    real = climod.load_product("prisma-browser")
    object.__setattr__(real, "output_dir", tmp_path / "prisma-browser-sdk")
    monkeypatch.setattr(climod, "load_product", lambda name: real)

    rc = main(["cli", "build", "prisma-browser"])
    assert rc == 0
    root = tmp_path / "prisma-browser-cli"
    pyproject = (root / "pyproject.toml").read_text()
    assert "prisma-browser-sdk" in pyproject and "prisma_browser" not in pyproject.split("dependencies")[1].split("]")[0].replace("prisma-browser-sdk", "")
    assert "prisma-browser-cli = " in pyproject
    assert (root / "README.md").exists() and (root / "noxfile.py").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    assert (root / ".env.example").read_text()  # non-empty (auth vars)
    assert (root / "prisma_browser_cli" / "_generated" / "app.py").exists()
    assert (root / "prisma_browser_cli" / "main.py").exists()
```

(If `LoadedProduct` is a frozen dataclass and `object.__setattr__`/property monkeypatch is awkward, instead build a thin wrapper object exposing `.config`, `.base_dir`, `.output_dir`, `.context`, `.auth` pointing at the real product but with `output_dir` in `tmp_path`, and monkeypatch `load_product` to return it. The contract: the build must NOT write into the real `../prisma-browser-sdk` tree.)

- [ ] **Step 2: Run → PASS (not skip)**

Run: `uv run pytest tests/test_cli_emitted_real.py::test_real_cli_build_emits_full_project -v`
Expected: PASS. If `render_scaffold` errors on a missing context var for the real product, add it to `build_cli_scaffold_context` (it inherits from `loaded.context`, so this should not happen — but the real `loaded.context` is the source of truth).

- [ ] **Step 3: Full suite + commit**

Run: `uv run pytest tests/ -q && uv run ruff check src/phantasos tests/ && uv run mypy src/phantasos/generator src/phantasos/cli.py`
```bash
git add tests/test_cli_emitted_real.py
git commit -m "test(cli-gen): real-SDK cli build emits a full phantasos-grade project"
```

---

## Task 8: Spec update — pyproject is scaffold-owned

**Files:**
- Modify: `docs/superpowers/specs/2026-06-09-cli-generator-design.md`

- [ ] **Step 1:** In the "Generated CLI project (runtime behavior)" and "Augmentation & extensibility" sections, change the ownership table so `pyproject.toml` (and README, noxfile, CI, `.env.example`, mkdocs, dotfiles) are **scaffold-owned (overwrite every build)** rather than hand-owned emit-once. State that the CLI reuses `render_scaffold` with a CLI context, and that custom-command deps are added via `cli.yml project.dependencies`. Keep `main.py`/`custom/`/`hooks.py` as hand-owned emit-once.

- [ ] **Step 2: Commit**
```bash
git add docs/superpowers/specs/2026-06-09-cli-generator-design.md
git commit -m "docs: CLI pyproject/project shell is scaffold-owned (Phase 3g)"
```

---

## Self-review (completed during authoring)

- **Combine goals covered:** scaffold reuse via `render_scaffold` (Tasks 4,6); SDK-distribution dep fix (Task 4 context + Task 6 integration assert; verified on the real SDK in Task 7); console-script (Task 1 + context); `.env.example` (Tasks 2,4); README (Task 5); pyproject ownership move + spec update (Tasks 6,8). SDK component tests gated off for the CLI via `has_*`=False (Task 4, asserted in Task 6). SDK build unaffected: pyproject `[project.scripts]` and `.env.example` are both guarded on `is defined`/whitespace-skip (Tasks 1,2 assert this).
- **Placeholder scan:** none — every step has concrete code. Two steps flag a known-awkward detail (the `LoadedProduct` monkeypatch in Task 7; the `cli_distribution` derivation in Task 4) with the test as the authoritative contract.
- **Type/name consistency:** `build_cli_scaffold_context(loaded, ir, cli_cfg)` (Task 4) is called with those args in Task 6; `cli_overrides_dir()` (Task 5) is imported in Tasks 5,6; `CliConfig.project` (Task 3) is read in Task 4; `scripts`/`auth_env_vars` context keys (Task 4) match the templates (Tasks 1,2). `render_cli` losing its `distribution`/`sdk_dependency` params (Task 6) — Task 6 Step 3 explicitly removes the Phase-2b pyproject tests that referenced them.

## Risks the review pass should scrutinize
1. **`render_scaffold` overwrites vs the regen contract.** Confirm it does NOT delete `_generated/`, `main.py`, `custom/`, `hooks.py` (it only writes its own template set — verify against `scaffold.py`). Order of `render_cli` vs `render_scaffold` in `cli build`.
2. **StrictUndefined coverage.** The CLI context inherits `loaded.context`, but `scripts`/`auth_env_vars` are new and the templates guard them with `is defined` — confirm no scaffold template references a var the CLI context lacks (esp. anything SDK-only beyond the `has_*` gates).
3. **Component-test gating.** With `has_auth=False` etc., do ALL SDK-specific test templates render empty, or does any reference a var unconditionally before the `{% if %}`? (e.g. a module docstring outside the gate.) If so it would emit a stray file — verify each `scaffold/tests/*.jinja` gates the WHOLE body.
4. **`conftest.py.jinja` is ungated and SDK-worded** — for the CLI it renders a "for the {{ package }} SDK" conftest that puts the project root on `sys.path`. Harmless for the CLI? Or should the CLI override it? Decide.
5. **`cli_distribution` derivation** (`-sdk` → `-cli`) — is it robust for distributions that don't end in `-sdk`? The `cli.yml project.distribution` is the clean escape hatch.
6. **pyproject `packages = ["{{ package }}"]`** with `package = prisma_browser_cli` — confirm hatchling will package the CLI correctly (the `_generated`/`custom` subpackages included).
