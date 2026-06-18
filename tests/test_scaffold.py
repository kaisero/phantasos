"""Tests for the project-scaffold renderer."""

from pathlib import Path
from typing import Any

from phantasos import scaffold


def _ctx(**over: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "package": "acme",
        "distribution": "acme-sdk",
        "has_auth": True,
        "has_pagination": False,
        "repo_url": "https://x/acme-sdk",
    }
    base.update(over)
    return base


def test_scaffold_renders_builtin_and_strips_jinja(tmp_path: Path) -> None:
    builtin = tmp_path / "scaffold"
    (builtin / ".github" / "workflows").mkdir(parents=True)
    (builtin / "pyproject.toml.jinja").write_text(
        "name = '{{ distribution }}'\n", "utf-8"
    )
    (builtin / ".github" / "workflows" / "ci.yml.jinja").write_text(
        "on: [push]\n", "utf-8"
    )
    # non-jinja: copied verbatim
    (builtin / ".editorconfig").write_text("root = true\n", "utf-8")
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
    ctx = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://x/y",
        "package": "acme",
        "dependencies": ["pydantic >= 2.11"],
        "python_versions": ["3.12"],
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
        "has_retry": True,
        "config_class_name": "AcmeConfiguration",
    }
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    pp = (out / "pyproject.toml").read_text()
    assert 'name = "acme-sdk"' in pp and "pydantic >= 2.11" in pp
    assert 'packages = ["acme"]' in pp


def test_builtin_noxfile_renders(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://x/y",
        "package": "acme",
        "dependencies": ["pydantic"],
        "python_versions": ["3.11", "3.12"],
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
        "has_retry": True,
        "config_class_name": "AcmeConfiguration",
    }
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
    ctx = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://github.com/x/acme-sdk",
        "package": "acme",
        "dependencies": ["pydantic"],
        "python_versions": ["3.11", "3.12"],
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
        "has_retry": True,
        "config_class_name": "AcmeConfiguration",
        "has_docs": True,
        "site_name": "acme-sdk",
        "show_pagination_guide": True,
        "spec_title": "Acme API",
        "credentials": [
            {
                "name": "client_id",
                "env_var": "CLIENT_ID",
                "secret": False,
                "required": True,
            },
        ],
        "showcase": {
            "attr": "widgets",
            "has_create": True,
            "has_read": True,
            "has_list": True,
            "has_update": False,
            "has_delete": True,
            "list": {"method": "list_widgets"},
            "operations": {
                "create": {"method": "create_widget", "required_args": []},
                "read": {
                    "method": "get_widget_by_id",
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
                "list": {"method": "list_widgets", "required_args": []},
                "delete": {
                    "method": "delete_widget_by_id",
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
            },
        },
    }
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    wfs = sorted((out / ".github" / "workflows").glob("*.yml"))
    expected_wfs = {
        "ci.yml",
        "release.yml",
        "audit.yml",
        "secrets.yml",
        "codeql.yml",
        "docs.yml",
    }
    assert {p.name for p in wfs} >= expected_wfs
    for wf in wfs:
        parse(wf.read_text())  # raises on invalid YAML
    # mkdocs.yml uses !!python/name: tags (pymdownx superfences); safe YAML
    # loaders cannot resolve them — use unsafe loader only for syntax validation.
    import yaml

    yaml.unsafe_load((out / "mkdocs.yml").read_text())


def test_builtin_meta_files_render(tmp_path: Path) -> None:
    out = tmp_path / "sdk"
    out.mkdir()
    ctx = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "sec@example.com",
        "repo_url": "https://x/y",
        "package": "acme",
        "dependencies": ["pydantic"],
        "python_versions": ["3.12"],
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
        "has_retry": True,
        "config_class_name": "AcmeConfiguration",
    }
    scaffold.render_scaffold(scaffold.builtin_dir(), None, out, ctx)
    assert (out / "CHANGELOG.md").exists()
    assert "acme-sdk" in (out / "CHANGELOG.md").read_text()
    assert (out / "CONTRIBUTING.md").exists()
    assert "sec@example.com" in (out / "SECURITY.md").read_text()


def test_builtin_component_tests_gating(tmp_path: Path) -> None:
    base_ctx = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://x/y",
        "package": "acme",
        "dependencies": ["pydantic"],
        "python_versions": ["3.12"],
        "config_class_name": "AcmeConfiguration",
    }
    # all components present -> all 4 component tests + conftest render
    out_all = tmp_path / "all"
    out_all.mkdir()
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        None,
        out_all,
        {
            **base_ctx,
            "has_auth": True,
            "has_pagination": True,
            "has_errors": True,
            "has_facade": True,
            "has_retry": True,
        },
    )
    t = out_all / "tests"
    assert (t / "conftest.py").exists()
    for name in (
        "test_auth.py",
        "test_pagination.py",
        "test_errors.py",
        "test_facade.py",
    ):
        assert (t / name).exists(), name
    # only auth present -> only test_auth renders; others skipped
    out_auth = tmp_path / "authonly"
    out_auth.mkdir()
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        None,
        out_auth,
        {
            **base_ctx,
            "has_auth": True,
            "has_pagination": False,
            "has_errors": False,
            "has_facade": False,
            "has_retry": False,
        },
    )
    t2 = out_auth / "tests"
    assert (t2 / "test_auth.py").exists()
    assert not (t2 / "test_pagination.py").exists()
    assert not (t2 / "test_errors.py").exists()
    assert not (t2 / "test_facade.py").exists()
    # the rendered test_auth.py is valid Python
    import ast

    ast.parse((t2 / "test_auth.py").read_text())


def test_scaffold_retry_test_gated(tmp_path: Path) -> None:
    base = {
        "distribution": "acme-sdk",
        "description": "d",
        "license": "Apache-2.0",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://x/y",
        "package": "acme",
        "dependencies": ["pydantic"],
        "python_versions": ["3.12"],
        "config_class_name": "AcmeConfiguration",
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
    }
    out_on = tmp_path / "on"
    out_on.mkdir()
    scaffold.render_scaffold(
        scaffold.builtin_dir(), None, out_on, {**base, "has_retry": True}
    )
    assert (out_on / "tests" / "test_retry.py").exists()
    out_off = tmp_path / "off"
    out_off.mkdir()
    scaffold.render_scaffold(
        scaffold.builtin_dir(), None, out_off, {**base, "has_retry": False}
    )
    assert not (out_off / "tests" / "test_retry.py").exists()
