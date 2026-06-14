from pathlib import Path

import pytest
from tools import context_docs as cd


def _pkg(tmp_path: Path) -> Path:
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "alpha.py").write_text(
        '"""Alpha module does A.\n\nmore.\n"""\n'
        "def public_fn(x, y):\n"
        '    """Run the thing."""\n'
        "    return x\n\n"
        "def _private():\n"
        "    return 1\n"
    )
    (pkg / "beta.py").write_text(
        '"""Beta module."""\nclass Widget:\n    """A widget."""\n    pass\n'
    )
    return pkg


def test_module_map_lists_modules_with_first_docline(tmp_path: Path) -> None:
    out = cd.module_map(_pkg(tmp_path))
    assert "- `alpha.py` — Alpha module does A." in out
    assert "- `beta.py` — Beta module." in out
    assert "__init__.py" not in out


def test_public_api_extracts_public_only(tmp_path: Path) -> None:
    out = cd.public_api(_pkg(tmp_path))
    assert "`public_fn(x, y)` — Run the thing." in out
    assert "class `Widget` — A widget." in out
    assert "_private" not in out


def test_inject_replaces_between_markers_idempotently() -> None:
    text = "head\n<!-- GENERATED:api -->\nOLD\n<!-- /GENERATED:api -->\ntail\n"
    once = cd.inject(text, "api", "NEW")
    twice = cd.inject(once, "api", "NEW")
    assert "NEW" in once and "OLD" not in once
    assert once == twice
    assert once.startswith("head") and once.rstrip().endswith("tail")


def test_inject_missing_markers_raises() -> None:
    with pytest.raises(ValueError):
        cd.inject("no markers here", "api", "x")
