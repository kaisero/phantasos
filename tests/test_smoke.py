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
