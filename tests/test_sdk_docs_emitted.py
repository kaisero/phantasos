# tests/test_sdk_docs_emitted.py
from pathlib import Path
from typing import Any

from phantasos import scaffold


def _ctx(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "package": "prisma_browser",
        "library": "urllib3",
        "base_url": "https://x",
        "spec_version": "1",
        "spec_title": "Prisma",
        "has_auth": True,
        "has_pagination": True,
        "has_errors": True,
        "has_facade": True,
        "has_retry": True,
        "has_docs": True,
        "config_class_name": "C",
        "distribution": "prisma-browser-sdk",
        "description": "d",
        "author": "A",
        "author_email": "a@b.c",
        "repo_url": "https://github.com/x/y",
        "license": "Apache-2.0",
        "python_versions": ["3.12"],
        "dependencies": [],
        "site_name": "prisma-browser-sdk",
        "credentials": [
            {
                "name": "client_id",
                "env_var": "CLIENT_ID",
                "secret": False,
                "required": True,
            },
            {
                "name": "client_secret",
                "env_var": "CLIENT_SECRET",
                "secret": True,
                "required": True,
            },
        ],
        "show_pagination_guide": True,
        "showcase": {
            "attr": "applications",
            "has_create": True,
            "has_read": True,
            "has_list": True,
            "has_update": False,
            "has_delete": True,
            "list": {"method": "list_applications"},
            "operations": {
                "create": {
                    "method": "create_application",
                    "required_args": [
                        {"name": "type", "kind": "path", "placeholder": "WEB"},
                        {
                            "name": "create_or_replace_app_input",
                            "kind": "body",
                            "body_model": "CreateOrReplaceAppInput",
                        },
                    ],
                },
                "read": {
                    "method": "get_application_by_id",
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
                "list": {"method": "list_applications", "required_args": []},
                "delete": {
                    "method": "delete_application_by_id",
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
            },
        },
    }
    base.update(over)
    return base


def test_docs_emitted_when_has_docs(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "create_application" in crud
    assert "get_application_by_id" in crud
    assert "delete_application_by_id" in crud
    # update omitted (has_update False) -> no patch example
    assert "## Update" not in crud
    assert (tmp_path / "mkdocs.yml").exists()
    assert "docstring_style: sphinx" in (tmp_path / "mkdocs.yml").read_text()
    assert (tmp_path / "docs/_hooks.py").exists()
    auth = (tmp_path / "docs/guides/authentication.md").read_text()
    assert "CLIENT_SECRET" in auth


def test_no_docs_when_flag_false(tmp_path: Path) -> None:
    scaffold.render_scaffold(
        scaffold.builtin_dir(), None, tmp_path, _ctx(has_docs=False)
    )
    assert not (tmp_path / "mkdocs.yml").exists()
    # render_scaffold does dest.parent.mkdir() before the whitespace-skip check,
    # so an EMPTY docs/ dir may be created even when every template gates out.
    # Assert no doc FILES were emitted (not that the dir is absent).
    assert not list((tmp_path / "docs").rglob("*.md"))
    assert not (tmp_path / "docs" / "_hooks.py").exists()


def test_getting_started_handles_read_body_arg(tmp_path: Path) -> None:
    # A showcase with no list op falls back to the read op in Getting Started; if
    # that read op has a body arg, the template must render BodyModel(...) (not
    # crash on a missing 'placeholder' under StrictUndefined).
    showcase: dict[str, Any] = {
        "attr": "things",
        "has_create": False,
        "has_read": True,
        "has_list": False,
        "has_update": False,
        "has_delete": False,
        "list": None,
        "operations": {
            "read": {
                "method": "query_thing",
                "required_args": [
                    {"name": "id", "kind": "path", "placeholder": "<id>"},
                    {"name": "thing_query", "kind": "body", "body_model": "ThingQuery"},
                ],
            },
        },
    }
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        None,
        tmp_path,
        _ctx(showcase=showcase, show_pagination_guide=False, has_pagination=False),
    )
    gs = (tmp_path / "docs/getting-started.md").read_text()
    assert "query_thing(" in gs
    assert "thing_query=ThingQuery(...)" in gs


def test_mkdocs_enables_griffe_pydantic_and_filters(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    mk = (tmp_path / "mkdocs.yml").read_text()
    assert "griffe_pydantic" in mk
    assert "show_if_no_docstring: true" in mk
    # boilerplate the aggressive filter must hide. NB: mkdocstrings filters are
    # re.search patterns, so the unanchored-tail "!^oneof_schema_" matches every
    # oneof_schema_<n>_validator member — and avoids a backslash that would not
    # survive the verbatim YAML round-trip.
    for pat in (
        "!^to_dict$",
        "!^model_config$",
        "!^additional_properties$",
        "!^actual_instance$",
        "!^oneof_schema_",
    ):
        assert pat in mk, pat
    pp = (tmp_path / "pyproject.toml").read_text()
    assert "griffe-pydantic" in pp


def test_mkdocs_yaml_safe_with_colon_in_text(tmp_path: Path) -> None:
    # Free-text site_name/description containing ": " must not break the YAML.
    import yaml

    desc = "Acme: the next-gen API SDK"
    scaffold.render_scaffold(
        scaffold.builtin_dir(),
        None,
        tmp_path,
        _ctx(description=desc, site_name="Acme: SDK"),
    )
    data = yaml.unsafe_load((tmp_path / "mkdocs.yml").read_text())
    assert data["site_description"] == desc
    assert data["site_name"] == "Acme: SDK"
