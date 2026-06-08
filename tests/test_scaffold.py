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


def test_builtin_pyproject_renders(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "a@b.c", "repo_url": "https://x/y",
           "package": "acme", "dependencies": ["pydantic >= 2.11"],
           "python_versions": ["3.12"], "has_auth": True, "has_pagination": True,
           "has_errors": True, "has_facade": True}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    pp = (out / "pyproject.toml").read_text()
    assert 'name = "acme-sdk"' in pp and "pydantic >= 2.11" in pp
    assert 'packages = ["acme"]' in pp


def test_builtin_noxfile_renders(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "a@b.c", "repo_url": "https://x/y",
           "package": "acme", "dependencies": ["pydantic"], "python_versions": ["3.11", "3.12"],
           "has_auth": True, "has_pagination": True, "has_errors": True, "has_facade": True}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    nox_src = (out / "noxfile.py").read_text()
    assert "PYTHON_VERSIONS = ['3.11', '3.12']" in nox_src
    assert "--cov=acme" in nox_src
    assert (out / ".pre-commit-config.yaml").exists()
    import ast
    ast.parse(nox_src)  # the rendered noxfile must be valid Python


def test_builtin_workflows_render_valid_yaml(tmp_path: Path) -> None:
    from ruamel.yaml import YAML

    parse = YAML(typ="safe").load

    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "a@b.c", "repo_url": "https://github.com/x/acme-sdk",
           "package": "acme", "dependencies": ["pydantic"], "python_versions": ["3.11", "3.12"],
           "has_auth": True, "has_pagination": True, "has_errors": True, "has_facade": True}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    wfs = sorted((out / ".github" / "workflows").glob("*.yml"))
    assert {p.name for p in wfs} >= {"ci.yml", "release.yml", "audit.yml", "secrets.yml", "codeql.yml", "docs.yml"}
    for wf in wfs:
        parse(wf.read_text())  # raises on invalid YAML
    parse((out / "mkdocs.yml").read_text())


def test_builtin_meta_files_render(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {"distribution": "acme-sdk", "description": "d", "license": "Apache-2.0",
           "author": "A", "author_email": "sec@example.com", "repo_url": "https://x/y",
           "package": "acme", "dependencies": ["pydantic"], "python_versions": ["3.12"],
           "has_auth": True, "has_pagination": True, "has_errors": True, "has_facade": True}
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    assert (out / "CHANGELOG.md").exists()
    assert "acme-sdk" in (out / "CHANGELOG.md").read_text()
    assert (out / "CONTRIBUTING.md").exists()
    assert "sec@example.com" in (out / "SECURITY.md").read_text()
