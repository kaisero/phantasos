"""Unit tests for the smoke import/operation-count check."""

import sys
from pathlib import Path

from sdkgen import smoke


def _make_generated_pkg(project_dir: Path, pkgname: str, broken: bool = False) -> None:
    """Write a tiny generated-style package under ``project_dir``."""
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
    if broken:
        (pkg / "broken.py").write_text("import does_not_exist_xyz\n", encoding="utf-8")


def test_smoke_counts_imports_and_operations(tmp_path: Path) -> None:
    _make_generated_pkg(tmp_path, "demo_ok")
    try:
        result = smoke.smoke(str(tmp_path), "demo_ok")
    finally:
        sys.path[:] = [p for p in sys.path if p != str(tmp_path)]
        for name in list(sys.modules):
            if name == "demo_ok" or name.startswith("demo_ok."):
                del sys.modules[name]

    assert result["failed"] == 0
    assert result["imported"] >= 1
    assert result["failures"] == []
    # Only list_things + get_thing count; the _with_http_info / _without_preload_content
    # helpers are excluded.
    assert result["operations"] == 2


def test_smoke_reports_import_failures(tmp_path: Path) -> None:
    _make_generated_pkg(tmp_path, "demo_bad", broken=True)
    try:
        result = smoke.smoke(str(tmp_path), "demo_bad")
    finally:
        sys.path[:] = [p for p in sys.path if p != str(tmp_path)]
        for name in list(sys.modules):
            if name == "demo_bad" or name.startswith("demo_bad."):
                del sys.modules[name]

    assert result["failed"] == 1
    assert any(name.endswith("broken") for name, _ in result["failures"])
