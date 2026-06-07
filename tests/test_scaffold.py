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
