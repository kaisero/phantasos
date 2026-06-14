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
    pkg = _pkg(tmp_path)
    files = sorted(pkg.glob("*.py"))
    out = cd.module_map(files)
    assert "- `alpha.py` — Alpha module does A." in out
    assert "- `beta.py` — Beta module." in out
    assert "__init__.py" not in out


def test_public_api_extracts_public_only(tmp_path: Path) -> None:
    pkg = _pkg(tmp_path)
    files = sorted(pkg.glob("*.py"))
    out = cd.public_api(files)
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


def test_inject_out_of_order_markers_raises() -> None:
    # end marker before start marker
    text = "<!-- /GENERATED:api -->\n<!-- GENERATED:api -->\n"
    with pytest.raises(ValueError, match="out of order"):
        cd.inject(text, "api", "x")


def test_signature_includes_posonly_and_kwonly(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg2"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def f(a, /, b, *, c): pass\n")
    files = sorted(pkg.glob("*.py"))
    out = cd.public_api(files)
    assert "`f(a, b, c)`" in out


def test_module_map_no_trailing_dash_for_undocumented(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg3"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "nodoc.py").write_text("x = 1\n")
    files = sorted(pkg.glob("*.py"))
    out = cd.module_map(files)
    assert "- `nodoc.py`" in out
    assert "- `nodoc.py` —" not in out


def test_public_api_no_trailing_dash_for_undocumented(tmp_path: Path) -> None:
    pkg = tmp_path / "pkg4"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def fn(): pass\nclass Cls: pass\n")
    files = sorted(pkg.glob("*.py"))
    out = cd.public_api(files)
    assert "`fn()`" in out
    assert "`fn()` —" not in out
    assert "class `Cls`" in out
    assert "class `Cls` —" not in out


def test_render_unknown_kind_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown block kind"):
        cd.render("nonexistent", [])


# ---------------------------------------------------------------------------
# expand() tests
# ---------------------------------------------------------------------------


def _tree(tmp_path: Path) -> Path:
    """Build a temp tree:
    root/
      a.py
      b.py
      sub/
        c.py
        d.txt
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.py").write_text("# a\n")
    (root / "b.py").write_text("# b\n")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.py").write_text("# c\n")
    (sub / "d.txt").write_text("text\n")
    return root


def test_expand_single_explicit_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    monkeypatch.setattr(cd, "REPO", root)
    result = cd.expand(["a.py"])
    assert result == [root / "a.py"]


def test_expand_star_py_returns_top_level_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    monkeypatch.setattr(cd, "REPO", root)
    result = cd.expand(["*.py"])
    assert result == sorted([root / "a.py", root / "b.py"])
    # sub/c.py must NOT appear
    assert not any("sub" in str(p) for p in result)


def test_expand_globstar_returns_nested_py(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    monkeypatch.setattr(cd, "REPO", root)
    result = cd.expand(["**/*.py"])
    paths = [p.name for p in result]
    assert "a.py" in paths
    assert "b.py" in paths
    assert "c.py" in paths
    # no .txt files
    assert "d.txt" not in paths


def test_expand_sorted_and_deduped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _tree(tmp_path)
    monkeypatch.setattr(cd, "REPO", root)
    # Two overlapping patterns both match a.py and b.py
    result = cd.expand(["*.py", "a.py"])
    assert result == sorted(set(result))  # sorted
    assert len(result) == len(set(result))  # deduped
    # Should still just be [a.py, b.py]
    assert result == sorted([root / "a.py", root / "b.py"])


# ---------------------------------------------------------------------------
# main() / --check tests
# ---------------------------------------------------------------------------

_MARKER_DOC = """\
# Doc

<!-- GENERATED:module-map -->
PLACEHOLDER
<!-- /GENERATED:module-map -->

end
"""


def _setup_main_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """Set up a temp CONTEXT dir + pkg dir; patch cd.CONTEXT and cd.BLOCKS."""
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    doc = context_dir / "test.md"
    doc.write_text(_MARKER_DOC)

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text('"""Module doc."""\n')

    monkeypatch.setattr(cd, "CONTEXT", context_dir)
    monkeypatch.setattr(cd, "REPO", tmp_path)
    # BLOCKS now uses a 3-tuple with a patterns list
    monkeypatch.setattr(cd, "BLOCKS", [("test.md", "module-map", ["pkg/*.py"])])

    return context_dir, doc


def test_main_check_returns_1_when_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _context_dir, _doc = _setup_main_env(tmp_path, monkeypatch)
    # The doc has "PLACEHOLDER" which differs from what render() produces.
    assert cd.main(["--check"]) == 1


def test_main_write_then_check_returns_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _context_dir, _doc = _setup_main_env(tmp_path, monkeypatch)
    # Write mode should update the doc.
    assert cd.main([]) == 0
    # After writing, --check should find it current.
    assert cd.main(["--check"]) == 0


def test_main_check_returns_1_not_crash_on_missing_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context_dir = tmp_path / "context"
    context_dir.mkdir()
    doc = context_dir / "test.md"
    doc.write_text("no markers here\n")

    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    monkeypatch.setattr(cd, "CONTEXT", context_dir)
    monkeypatch.setattr(cd, "REPO", tmp_path)
    monkeypatch.setattr(cd, "BLOCKS", [("test.md", "module-map", ["pkg/*.py"])])

    # Should return 1 cleanly, not raise.
    result = cd.main(["--check"])
    assert result == 1
