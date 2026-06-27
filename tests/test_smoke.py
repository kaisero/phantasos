"""Unit + integration tests for the isolated smoke check."""

from pathlib import Path

import pytest

from phantasos.generator.sdk import smoke
from phantasos.generator.sdk.smoke import SmokeError


def _make_generated_pkg(
    project_dir: Path, pkgname: str, *, broken: bool = False, reqs: str = ""
) -> None:
    """Write a tiny generated-style SDK (package + api + pyproject.toml)."""
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
    (project_dir / "pyproject.toml").write_text(
        f"[project]\nname = '{pkgname}'\nversion = '0'\nrequires-python = '>=3.9'\n"
        "[build-system]\nrequires = ['setuptools']\n"
        "build-backend = 'setuptools.build_meta'\n"
        f"[tool.setuptools]\npackages = ['{pkgname}']\n",
        encoding="utf-8",
    )
    if broken:
        (pkg / "broken.py").write_text("import does_not_exist_xyz\n", encoding="utf-8")


def test_count_operations_excludes_helpers(tmp_path: Path) -> None:
    _make_generated_pkg(tmp_path, "demo_ops")
    # Only list_things + get_thing count (the _with_http_info /
    # _without_preload_content helpers are excluded).
    assert smoke._count_operations(str(tmp_path), "demo_ops") == 2


def test_count_operations_federated_sums_nested_api_dirs(tmp_path: Path) -> None:
    # Federated layout: api/ files live under prisma_access/<slug>/api/, not at
    # the top level. The count must recurse and SUM across sub-packages.
    root = tmp_path / "prisma_access"
    objects_api = root / "objects" / "api"
    posture_api = root / "posture" / "api"
    objects_api.mkdir(parents=True)
    posture_api.mkdir(parents=True)
    (objects_api / "x_api.py").write_text(
        "class XApi:\n"
        "    def list_x(self):\n"
        "        return []\n"
        "    def get_x(self):\n"
        "        return None\n"
        "    def get_x_with_http_info(self):\n"
        "        return None\n",
        encoding="utf-8",
    )
    (posture_api / "y_api.py").write_text(
        "class YApi:\n    def list_y(self):\n        return []\n",
        encoding="utf-8",
    )
    # 2 (objects: list_x + get_x) + 1 (posture: list_y) = 3; helper excluded.
    assert smoke._count_operations(str(tmp_path), "prisma_access") == 3


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


def test_ensure_smoke_venv_missing_pyproject(tmp_path: Path) -> None:
    proj = tmp_path / "noproj"
    (proj / "pkg").mkdir(parents=True)
    with pytest.raises(SmokeError, match="pyproject"):
        smoke._ensure_smoke_venv(proj)


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
