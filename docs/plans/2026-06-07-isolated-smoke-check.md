# Isolated Smoke Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the smoke check's import-walk in an isolated, cached venv built from the generated SDK's *own* declared dependencies, so phantasos no longer needs the artifact's runtime deps (`pydantic`, `urllib3`, …) in its own environment.

**Architecture:** Split `smoke()` into two parts — the **operations count** (pure regex over `api/*_api.py`, stays in-process) and the **import-walk** (now run in a throwaway, requirements-hashed venv via a sanitized subprocess). The venv is provisioned with stdlib `venv` + the venv's own `pip`, cached under `~/.cache/phantasos/smoke-envs/<hash>`. A `--no-smoke` / `PHANTASOS_SKIP_SMOKE` opt-out skips the isolated check. The `generated` optional-dependency extra and the `smoke` dependency group are dropped.

**Tech Stack:** Python 3.11+ (stdlib: `venv`, `subprocess`, `hashlib`, `json`, `tempfile`, `shutil`, `os`, `re`, `pathlib`), pytest, nox, ruff, mypy. No new runtime deps. Design + rationale: `docs/specs/2026-06-07-isolated-smoke-check-design.md`.

---

## Confirmed decisions (from review)

1. **Provisioner:** stdlib `venv` + the venv's `pip`. Single code path — **no uv fast-path** (YAGNI; don't assume pip users have uv).
2. **Cache** the smoke venv under `~/.cache/phantasos/smoke-envs/<sha256(requirements.txt)>`, reused across builds.
3. **Opt-out:** `--no-smoke` CLI flag and `PHANTASOS_SKIP_SMOKE` env var.
4. **Drop** the `generated` extra and the `smoke` dependency group; phantasos base deps stay `ruamel.yaml` + `jinja2`.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/phantasos/smoke.py` | ops-count (in-process) + isolated import-walk (cached venv + sanitized subprocess); `SmokeError` | Rewrite |
| `src/phantasos/__init__.py` | `build(..., run_smoke=True)` threads the opt-out into `smoke()` | Modify (`build` sig + step 6) |
| `src/phantasos/cli.py` | `--no-smoke` flag; print "smoke skipped" when applicable | Modify |
| `tests/test_smoke.py` | rework for the venv model (add `requirements.txt`; no more `sys.modules` cleanup); add skip + missing-reqs cases | Rewrite |
| `pyproject.toml` | drop `generated` extra + `smoke` group; add `smoke.py` to ruff S603 ignore | Modify |
| `noxfile.py` | `smoke` session: `_sync(session)` (no smoke group) | Modify |
| `README.md` | `pip install -e .` (drop `[generated]`); note isolated smoke | Modify |
| `.github/workflows/ci.yml` | bump smoke cache key (now also holds `smoke-envs/`) | Modify |

---

### Task 1: Smoke scaffolding — `SmokeError`, env sanitizer, ops-count, venv-python path

**Files:**
- Modify: `src/phantasos/smoke.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing tests** (replace the whole file — the old in-process tests are superseded)

```python
# tests/test_smoke.py
"""Unit + integration tests for the isolated smoke check."""

import os
from pathlib import Path

import pytest

from phantasos import smoke
from phantasos.smoke import SmokeError


def _make_generated_pkg(
    project_dir: Path, pkgname: str, *, broken: bool = False, reqs: str = ""
) -> None:
    """Write a tiny generated-style SDK (package + api + requirements.txt)."""
    pkg = project_dir / pkgname
    api = pkg / "api"
    api.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (api / "__init__.py").write_text("", encoding="utf-8")
    (api / "things_api.py").write_text(
        "class ThingsApi:\n"
        "    def list_things(self):\n"
        "        return []\n"
        "    def get_thing(self):\n"
        "        return None\n"
        "    def list_things_with_http_info(self):\n"
        "        return None\n"
        "    def get_thing_without_preload_content(self):\n"
        "        return None\n",
        encoding="utf-8",
    )
    (project_dir / "requirements.txt").write_text(reqs, encoding="utf-8")
    if broken:
        (pkg / "broken.py").write_text("import does_not_exist_xyz\n", encoding="utf-8")


def test_count_operations_excludes_helpers(tmp_path: Path) -> None:
    _make_generated_pkg(tmp_path, "demo_ops")
    # Only list_things + get_thing count (the _with_http_info /
    # _without_preload_content helpers are excluded).
    assert smoke._count_operations(str(tmp_path), "demo_ops") == 2


def test_sanitized_env_strips_leaky_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIRTUAL_ENV", "/parent/venv")
    monkeypatch.setenv("PYTHONPATH", "/parent/src")
    monkeypatch.setenv("PYTHONHOME", "/parent/home")
    monkeypatch.setenv("KEEP_ME", "yes")
    env = smoke._sanitized_env()
    assert "VIRTUAL_ENV" not in env
    assert "PYTHONPATH" not in env
    assert "PYTHONHOME" not in env
    assert env["KEEP_ME"] == "yes"
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -q`
Expected: FAIL — `AttributeError: module 'phantasos.smoke' has no attribute '_count_operations'` / `SmokeError` import error.

- [ ] **Step 3: Rewrite `smoke.py` with the scaffolding** (full file; import-walk added in Task 3, orchestration finalized in Task 4)

```python
"""Smoke check: import every generated module (in isolation) and count operations."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path
from typing import Any

from . import provision

_SKIP_ENV = "PHANTASOS_SKIP_SMOKE"
# Vars that would leak the *parent* environment into the isolated subprocess and
# defeat the isolation (parent packages shadowing the venv, interpreter breakage).
_STRIP = ("VIRTUAL_ENV", "PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP")


class SmokeError(RuntimeError):
    """Raised when the isolated smoke environment cannot be provisioned."""


def _sanitized_env() -> dict[str, str]:
    """A copy of os.environ with venv/python path vars stripped."""
    return {k: v for k, v in os.environ.items() if k not in _STRIP}


def _count_operations(project_dir: str, package: str) -> int:
    """Count public API operations by scanning api/*_api.py text (no imports needed)."""
    ops = 0
    api_dir = Path(project_dir) / package / "api"
    for f in sorted(api_dir.glob("*_api.py")):
        for m in re.finditer(r"^    def ([a-z][a-zA-Z0-9_]*)\(", f.read_text(), re.M):
            if not m.group(1).endswith(
                ("_with_http_info", "_without_preload_content")
            ):
                ops += 1
    return ops


def _venv_python(venv_dir: Path) -> Path:
    """Path to the interpreter inside a created venv (cross-platform)."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/smoke.py tests/test_smoke.py
git commit -m "refactor(smoke): scaffolding — SmokeError, env sanitizer, ops-count split"
```

---

### Task 2: Cached smoke venv provisioner

**Files:**
- Modify: `src/phantasos/smoke.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
# append to tests/test_smoke.py
def test_ensure_smoke_venv_creates_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path / "cache"))
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_v", reqs="")  # empty reqs -> offline, fast
    py = smoke._ensure_smoke_venv(proj)
    assert py.exists()
    assert (py.parent.parent / ".ready").exists()
    # Cached: a second call returns the same interpreter without rebuilding.
    py2 = smoke._ensure_smoke_venv(proj)
    assert py2 == py


def test_ensure_smoke_venv_missing_requirements(tmp_path: Path) -> None:
    proj = tmp_path / "noreqs"
    (proj / "pkg").mkdir(parents=True)
    with pytest.raises(SmokeError, match="requirements.txt"):
        smoke._ensure_smoke_venv(proj)
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -k ensure_smoke_venv -q`
Expected: FAIL — `AttributeError: module 'phantasos.smoke' has no attribute '_ensure_smoke_venv'`.

- [ ] **Step 3: Implement `_ensure_smoke_venv`** (append to `smoke.py`)

```python
def _ensure_smoke_venv(project_dir: Path) -> Path:
    """Create (or reuse) a cached venv holding the SDK's declared deps; return its python."""
    reqs = project_dir / "requirements.txt"
    if not reqs.exists():
        raise SmokeError(
            f"no requirements.txt in {project_dir}; cannot isolate the smoke check. "
            f"Pass --no-smoke to skip, or build a spec that emits one."
        )
    key = hashlib.sha256(reqs.read_bytes()).hexdigest()[:16]
    venv_dir = provision.cache_dir() / "smoke-envs" / key
    py = _venv_python(venv_dir)
    ready = venv_dir / ".ready"
    if ready.exists() and py.exists():
        return py
    shutil.rmtree(venv_dir, ignore_errors=True)
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    subprocess.run(  # noqa: S603
        [str(py), "-m", "pip", "install", "-q", "-r", str(reqs)],
        check=True,
        env=_sanitized_env(),
    )
    ready.write_text("")  # mark complete only after a successful install
    return py
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -k ensure_smoke_venv -q`
Expected: PASS (2 passed). The first test really creates a venv under `tmp_path/cache` (offline, empty requirements) — a few seconds.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/smoke.py tests/test_smoke.py
git commit -m "feat(smoke): cached, requirements-hashed venv provisioner"
```

---

### Task 3: Isolated import-walk (sanitized subprocess)

**Files:**
- Modify: `src/phantasos/smoke.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing tests** (append) — covers success, failure counting, and the env-leak guard

```python
# append to tests/test_smoke.py
def test_import_walk_counts_and_isolates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path / "cache"))
    # Leak a bogus PYTHONPATH in the parent; the subprocess must NOT inherit it.
    monkeypatch.setenv("PYTHONPATH", "/totally/bogus/path")
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_walk", reqs="")
    result = smoke._import_walk(str(proj), "demo_walk")
    assert result["failed"] == 0
    assert result["imported"] >= 1
    assert result["failures"] == []


def test_import_walk_reports_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path / "cache"))
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_broken", broken=True, reqs="")
    result = smoke._import_walk(str(proj), "demo_broken")
    assert result["failed"] == 1
    assert any(name.endswith("broken") for name, _ in result["failures"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -k import_walk -q`
Expected: FAIL — `AttributeError: module 'phantasos.smoke' has no attribute '_import_walk'`.

- [ ] **Step 3: Implement `_import_walk` + the walk script** (append to `smoke.py`)

```python
# Runs inside the isolated interpreter. project_dir is added to sys.path here
# (NOT via env) so the parent's PYTHONPATH stays stripped. Results go to a file
# to avoid mixing with anything the imported modules print to stdout.
_WALK_SRC = r"""
import importlib
import json
import pkgutil
import sys

project_dir, package, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, project_dir)
pkg = importlib.import_module(package)
ok = 0
failures = []
for mod in pkgutil.walk_packages(pkg.__path__, package + "."):
    try:
        importlib.import_module(mod.name)
        ok += 1
    except Exception as exc:  # noqa: BLE001 - record any import failure, keep going
        failures.append([mod.name, repr(exc)[:160]])
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump({"imported": ok, "failed": len(failures), "failures": failures}, fh)
"""


def _import_walk(project_dir: str, package: str) -> dict[str, Any]:
    """Import-check every module of the generated SDK in an isolated venv."""
    py = _ensure_smoke_venv(Path(project_dir))
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    out_path = Path(out)
    try:
        subprocess.run(  # noqa: S603
            [str(py), "-c", _WALK_SRC, project_dir, package, out],
            check=True,
            env=_sanitized_env(),
        )
        data: dict[str, Any] = json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        out_path.unlink(missing_ok=True)
    data["failures"] = [tuple(item) for item in data["failures"]]
    return data
```

- [ ] **Step 4: Run to verify they pass**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -k import_walk -q`
Expected: PASS (2 passed). The bogus `PYTHONPATH` in the first test is proven harmless because the subprocess env is sanitized.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/smoke.py tests/test_smoke.py
git commit -m "feat(smoke): isolated import-walk via sanitized subprocess"
```

---

### Task 4: `smoke()` orchestration + opt-out

**Files:**
- Modify: `src/phantasos/smoke.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
# append to tests/test_smoke.py
def test_smoke_combines_walk_and_ops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path / "cache"))
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_full", reqs="")
    result = smoke.smoke(str(proj), "demo_full")
    assert result["operations"] == 2
    assert result["failed"] == 0
    assert result["imported"] >= 1
    assert result["skipped"] is False


def test_smoke_skipped_via_env_does_not_build_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    monkeypatch.setenv("PHANTASOS_CACHE", str(cache))
    monkeypatch.setenv("PHANTASOS_SKIP_SMOKE", "1")
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_skip", reqs="")
    result = smoke.smoke(str(proj), "demo_skip")
    assert result["skipped"] is True
    assert result["operations"] == 2  # ops still counted (in-process, no deps)
    assert result["imported"] == 0 and result["failed"] == 0
    assert not (cache / "smoke-envs").exists()  # no venv was provisioned


def test_smoke_run_false_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHANTASOS_CACHE", str(tmp_path / "cache"))
    monkeypatch.delenv("PHANTASOS_SKIP_SMOKE", raising=False)
    proj = tmp_path / "proj"
    _make_generated_pkg(proj, "demo_norun", reqs="")
    result = smoke.smoke(str(proj), "demo_norun", run=False)
    assert result["skipped"] is True
```

- [ ] **Step 2: Run to verify they fail**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -k "combines or skipped or run_false" -q`
Expected: FAIL — `TypeError: smoke() got an unexpected keyword argument 'run'` (current `smoke` has no `run` param / `skipped` key).

- [ ] **Step 3: Implement `smoke()`** (append to `smoke.py`)

```python
def smoke(project_dir: str, package: str, *, run: bool = True) -> dict[str, Any]:
    """Verify a built SDK: count operations and (unless skipped) import-walk it.

    The import-walk runs in an isolated venv built from the SDK's own
    requirements.txt, so phantasos needs none of the SDK's runtime deps. Set
    run=False or PHANTASOS_SKIP_SMOKE to skip the import-walk (offline builds).
    """
    ops = _count_operations(project_dir, package)
    if not run or os.environ.get(_SKIP_ENV):
        return {
            "imported": 0,
            "failed": 0,
            "operations": ops,
            "failures": [],
            "skipped": True,
        }
    result = _import_walk(project_dir, package)
    result["operations"] = ops
    result["skipped"] = False
    return result
```

- [ ] **Step 4: Run to verify they pass (and the whole smoke file)**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest pytest tests/test_smoke.py -q`
Expected: PASS — all smoke tests green.

- [ ] **Step 5: Commit**

```bash
git add src/phantasos/smoke.py tests/test_smoke.py
git commit -m "feat(smoke): orchestrate ops-count + isolated walk with skip opt-out"
```

---

### Task 5: Thread `--no-smoke` through `build()` and the CLI

**Files:**
- Modify: `src/phantasos/__init__.py`, `src/phantasos/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** (append to `tests/test_cli.py`)

```python
# append to tests/test_cli.py
def test_build_passes_run_smoke_false(tmp_path, monkeypatch) -> None:
    import phantasos

    captured: dict[str, object] = {}

    def fake_smoke(project_dir, package, *, run=True):
        captured["run"] = run
        return {"imported": 0, "failed": 0, "operations": 0, "failures": [], "skipped": True}

    # Stub every pipeline step that needs Java / a real spec so we test only the
    # run_smoke wiring. build() writes _about.py into <project_dir>/<package>, so
    # point project_dir at tmp_path and create the package dir.
    monkeypatch.setattr("phantasos.smoke.smoke", fake_smoke)
    monkeypatch.setattr("phantasos.generate.generate", lambda *a, **k: None)
    monkeypatch.setattr("phantasos.render.vendor", lambda *a, **k: {})
    monkeypatch.setattr("phantasos.patches.apply_generic_patches", lambda pkg_dir: {})
    monkeypatch.setattr(
        "phantasos.preprocess.load", lambda spec: ({"info": {"version": "1"}}, object())
    )
    monkeypatch.setattr("phantasos.preprocess.clean", lambda spec, stats: None)
    monkeypatch.setattr("phantasos.preprocess.dump", lambda spec, yaml, path: None)

    from phantasos.config import SdkConfig

    cfg = SdkConfig(
        spec="s.yml", package="pkg", base_url="https://api/", project_dir=str(tmp_path)
    )
    (tmp_path / "pkg").mkdir()
    phantasos.build(cfg, run_smoke=False)
    assert captured["run"] is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 --with ruamel.yaml pytest tests/test_cli.py -k run_smoke -q`
Expected: FAIL — `TypeError: build() got an unexpected keyword argument 'run_smoke'`.

- [ ] **Step 3: Add `run_smoke` to `build()`** — in `src/phantasos/__init__.py`, change the signature and the step-6 call

Signature (add the keyword-only param):
```python
def build(
    config: SdkConfig,
    *,
    preprocess_hook: Callable[[Any], None] | None = None,
    patch_hook: Callable[[Path], None] | None = None,
    run_smoke: bool = True,
) -> dict[str, Any]:
```

Step 6 call:
```python
    # 6. smoke
    result = smoke.smoke(str(project_dir), config.package, run=run_smoke)
```

- [ ] **Step 4: Add `--no-smoke` to the CLI** — in `src/phantasos/cli.py`

Add the flag to the `build` subparser (after the `config` argument):
```python
    b.add_argument(
        "--no-smoke",
        action="store_true",
        help="skip the isolated import-check (offline/locked-down builds)",
    )
```

Pass it through and handle the skipped result. Replace the `build(...)` call and the result printing:
```python
            mod = _load_spec_module(config_path)
            result = build(
                mod.CONFIG,
                preprocess_hook=getattr(mod, "preprocess", None),
                patch_hook=getattr(mod, "patch", None),
                run_smoke=not args.no_smoke,
            )
        finally:
            os.chdir(cwd)
        s = result["smoke"]
        if s.get("skipped"):
            print(f"built {mod.CONFIG.package}: smoke skipped; operations: {s['operations']}")
            return 0
        print(
            f"built {mod.CONFIG.package}: imported {s['imported']} modules, "
            f"{s['failed']} failures; operations: {s['operations']}"
        )
        for name, err in s["failures"][:10]:
            print("  FAIL", name, err)
        return 1 if s["failed"] else 0
```

- [ ] **Step 5: Run to verify it passes**

Run: `PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 --with ruamel.yaml pytest tests/test_cli.py -q`
Expected: PASS — the new wiring test plus the existing CLI tests.

- [ ] **Step 6: Commit**

```bash
git add src/phantasos/__init__.py src/phantasos/cli.py tests/test_cli.py
git commit -m "feat: --no-smoke / run_smoke opt-out threaded through build() and CLI"
```

---

### Task 6: Drop the `generated` extra + `smoke` group; update nox, ruff, README

**Files:**
- Modify: `pyproject.toml`, `noxfile.py`, `README.md`

- [ ] **Step 1: Remove the `generated` extra** — in `pyproject.toml`, delete the block at lines 35–38:

```toml
[project.optional-dependencies]
# Deps the *generated* SDK imports at smoke/runtime — installed so `phantasos build`
# can import-check its own output. A built SDK declares these in its own pyproject.
generated = ["pydantic>=2", "urllib3>=2", "python-dateutil", "typing_extensions"]
```
(Delete all four lines, including the `[project.optional-dependencies]` header — nothing else uses it.)

- [ ] **Step 2: Remove the `smoke` dependency group** — in `pyproject.toml`, delete lines 58–59:

```toml
# Deps the generated SDK imports, so `nox -s smoke` can import-check its output.
smoke = ["pydantic>=2", "urllib3>=2", "python-dateutil", "typing_extensions"]
```

- [ ] **Step 3: Add `smoke.py` to ruff S603 ignore** — in `pyproject.toml` `[tool.ruff.lint.per-file-ignores]`, add:

```toml
# smoke.py shells out to the isolated venv's python/pip — trusted argv.
"src/phantasos/smoke.py" = ["S603"]
```

- [ ] **Step 4: Update the `smoke` nox session** — in `noxfile.py`, change its `_sync` call so it no longer installs the (now-deleted) smoke group:

```python
    _sync(session)
    session.run("phantasos", "build", "transformations/prisma-browser.py")
    session.run("phantasos", "build", "transformations/adem.py")
```

- [ ] **Step 5: Update the README Quickstart** — in `README.md`, replace the install line (`pip install -e ".[generated]"`) with `pip install -e .` and replace the old "Needs a JRE…" note. The new Quickstart body:

````markdown
## Quickstart
```bash
pip install -e .                       # phantasos itself — no SDK runtime deps needed
phantasos build transformations/prisma-browser.py
```
No system Java required — see [Requirements](#requirements). The OpenAPI Generator jar and
a JRE are fetched once to `~/.cache/phantasos` (override with `PHANTASOS_CACHE`). The smoke
step import-checks the built SDK in an isolated venv built from the SDK's own
`requirements.txt`, so phantasos needs none of the SDK's runtime deps; pass `--no-smoke` to
skip it (offline builds).
````

- [ ] **Step 6: Verify lint/type-check and the unit suite**

Run:
```bash
UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s lint type_check
PYTHONPATH=src uv run --no-project --python 3.12 --with pytest --with jinja2 --with ruamel.yaml pytest tests/ -q
```
Expected: ruff + mypy clean; tests pass. (No phantasos source imports pydantic/urllib3, so removing the extra/group cannot break imports.)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml noxfile.py README.md
git commit -m "chore: drop generated extra + smoke group; isolated smoke needs neither"
```

---

### Task 7: CI cache key + full verification (the real proof)

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Bump the smoke cache key** — `~/.cache/phantasos` now also holds `smoke-envs/`. In `.github/workflows/ci.yml`, change the smoke job's cache key:

```yaml
          key: phantasos-toolchain-oag7.22.0-jre17.0.19-smokeenv1
```

- [ ] **Step 2: Validate the workflow YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"`
Expected: `valid`.

- [ ] **Step 3: Full unit suite + coverage gate**

Run: `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos uv run nox --envdir $HOME/.nox-phantasos -s tests-3.12`
Expected: all pass, coverage ≥ 70%.

- [ ] **Step 4: The decisive end-to-end — build with NO SDK deps in the env**

Prove phantasos no longer needs `pydantic` itself. Run a build in an environment that has only phantasos's base deps (no `generated` extra), letting the isolated venv supply the SDK deps:
```bash
rm -rf ~/.cache/phantasos/smoke-envs
PYTHONPATH=src uv run --no-project --python 3.12 \
  --with jinja2 --with ruamel.yaml \
  python -m phantasos.cli build transformations/prisma-browser.py
```
Expected: builds successfully — `built prisma_browser: imported … modules, 0 failures; operations: …` — **with no pydantic/urllib3 in the invoking environment** (they get installed into the isolated smoke venv on the fly). This is the exact scenario that previously raised `ModuleNotFoundError: pydantic`.

- [ ] **Step 5: Verify the `--no-smoke` path**

```bash
PYTHONPATH=src uv run --no-project --python 3.12 --with jinja2 --with ruamel.yaml \
  python -m phantasos.cli build transformations/adem.py --no-smoke
```
Expected: `built adem: smoke skipped; operations: …` and exit 0, with no venv created under `~/.cache/phantasos/smoke-envs`.

- [ ] **Step 6: Confirm phantasos declares no SDK runtime deps**

Run: `grep -nE 'pydantic|urllib3|python-dateutil|typing_extensions' pyproject.toml || echo "NONE — clean"`
Expected: `NONE — clean` (the extra and group are gone; base deps remain `ruamel.yaml` + `jinja2`).

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: bump smoke cache key for the isolated smoke-env"
```

---

## Notes for the executor

- **Why a results file, not stdout:** imported SDK modules may print to stdout; the walk script writes JSON to a file path passed as argv so parsing is robust.
- **Why install deps (not the SDK) into the venv:** the cache key is `hash(requirements.txt)`, so the venv holds only the SDK's *deps* and is reused across rebuilds and across SDKs with identical deps. The SDK source itself is added to `sys.path` inside the walk script (not installed), so editing/rebuilding the SDK never invalidates the cached venv.
- **`.ready` marker:** written only after a successful `pip install`, so an interrupted install isn't mistaken for a usable cached venv.
- **Filesystem note (this sandbox only):** `~/.cache/phantasos` is on the home filesystem (symlinks OK), so venv creation works there even though the repo is on a symlink-less FUSE mount. `tmp_path` in tests resolves under `/tmp` (tmpfs), which also supports symlinks. Use `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/phantasos` for any `uv run` nox invocation.
- **Offline:** the isolated check needs network the first time it installs an SDK's deps; `--no-smoke` / `PHANTASOS_SKIP_SMOKE` is the escape hatch.
