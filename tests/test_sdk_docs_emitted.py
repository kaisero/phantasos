# tests/test_sdk_docs_emitted.py
"""Behavioral tests for the emitted docs site — WRAPPER surface.

The docs feature teaches `client.<object>.<clean_verb>(...)` (the typed resource
wrapper), never the raw `client.<resource>.<raw_method>()`. These tests render the
scaffold with a wrapper-shaped showcase context (object attr, clean verbs, `body=`
kwarg) and assert the emitted Markdown is wrapper-correct.
"""

import ast
from pathlib import Path
from typing import Any

import jinja2
import pytest

from phantasos import scaffold

_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

_GEN_REF = (
    Path(__file__).parent.parent
    / "src/phantasos/scaffold/docs/scripts/gen_ref_pages.py.jinja"
)


def _render_gen_ref(package: str) -> str:
    """Render the gen_ref_pages script template directly (package + has_docs only)."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_GEN_REF.parent)),
        keep_trailing_newline=True,
        autoescape=jinja2.select_autoescape(),
        undefined=jinja2.StrictUndefined,
    )
    return env.get_template(_GEN_REF.name).render(package=package, has_docs=True)


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
        # Wrapper showcase: `attr` is the singular object; each slot's `method` is
        # the CLEAN verb; the body arg is the literal `body` kwarg (has_update
        # False -> partial CRUD, no update example rendered).
        "showcase": {
            "attr": "application",
            "call_path": "application",  # single-spec: no sub-package prefix
            "has_create": True,
            "has_read": True,
            "has_list": True,
            "has_update": False,
            "has_delete": True,
            "list": {"method": "list"},
            "operations": {
                "create": {
                    "method": "create",
                    "example_override": None,
                    "required_args": [
                        {"name": "type", "kind": "path", "placeholder": "custom"},
                        {
                            "name": "body",
                            "kind": "body",
                            "body_model": "CreateOrReplaceAppInput",
                            "body_code": (
                                'CustomApplicationInput(\n    name="example",\n)'
                            ),
                        },
                    ],
                },
                "read": {
                    "method": "get",
                    "example_override": None,
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
                "list": {"method": "list", "required_args": []},
                "delete": {
                    "method": "delete",
                    "example_override": None,
                    "required_args": [
                        {"name": "id", "kind": "path", "placeholder": "<id>"}
                    ],
                },
            },
        },
    }
    base.update(over)
    return base


def test_docs_emitted_wrapper_surface(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    # Clean verbs on the object wrapper, with body=/id= kwargs.
    assert "client.application.create(" in crud
    assert "client.application.get(" in crud
    assert "client.application.delete(" in crud
    assert "    id=" in crud
    assert "    body=CustomApplicationInput(" in crud
    # NO raw-surface patterns may survive.
    assert "create_application" not in crud
    assert "get_application_by_id" not in crud
    assert "delete_application_by_id" not in crud
    assert "client.applications." not in crud
    # update omitted (has_update False) -> partial CRUD, no patch example
    assert "## Update" not in crud
    assert (tmp_path / "mkdocs.yml").exists()
    assert "docstring_style: sphinx" in (tmp_path / "mkdocs.yml").read_text()
    assert (tmp_path / "docs/_hooks.py").exists()
    auth = (tmp_path / "docs/guides/authentication.md").read_text()
    assert "CLIENT_SECRET" in auth


def test_pagination_uses_all_pages_not_paginate(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    pag = (tmp_path / "docs/guides/pagination.md").read_text()
    # The wrapper's built-in pagination, NOT the old client.paginate(...) helper.
    assert "client.application.list(all_pages=True).data" in pag
    assert "client.paginate(" not in pag


def test_getting_started_first_call_is_wrapper_list(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    gs = (tmp_path / "docs/getting-started.md").read_text()
    assert "client.application.list()" in gs
    assert "list_applications" not in gs


def test_architecture_teaches_wrapper_not_raw(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    arch = (tmp_path / "docs/architecture.md").read_text()
    assert "client.<object>" in arch
    # raw *Api is described as internal; the public surface is the wrapper.
    assert "Resource wrappers" in arch
    # the old raw "client.<resource>.<operation>" component row is gone.
    assert "client.<resource>.<operation>" not in arch


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
    # that read op has a body arg, the template must render its synthesized
    # body_code — and must not crash on a missing 'placeholder' key (body args
    # carry body_code, not placeholder) under StrictUndefined.
    showcase: dict[str, Any] = {
        "attr": "thing",
        "call_path": "thing",
        "has_create": False,
        "has_read": True,
        "has_list": False,
        "has_update": False,
        "has_delete": False,
        "list": None,
        "operations": {
            "read": {
                "method": "get",
                "example_override": None,
                "required_args": [
                    {"name": "id", "kind": "path", "placeholder": "<id>"},
                    {
                        "name": "body",
                        "kind": "body",
                        "body_model": "ThingQuery",
                        "body_code": "ThingQuery()",
                    },
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
    assert "client.thing.get(" in gs
    assert "body=ThingQuery()" in gs


def test_mkdocs_enables_griffe_pydantic_and_filters(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    mk = (tmp_path / "mkdocs.yml").read_text()
    assert "griffe_pydantic" in mk
    assert "show_if_no_docstring: true" in mk
    # The aggressive filter hides boilerplate AND the wrapper internals
    # (_bindings/_serialize/_select/_to_raw/_call/_fetch/_list) via the "!^_" rule.
    assert "!^_" in mk
    for pat in (
        "!^to_dict$",
        "!^model_config$",
        "!^additional_properties$",
        "!^actual_instance$",
        "!^oneof_schema_",
    ):
        assert pat in mk, pat
    # Tier 0: render the body model type in the signature, as a clickable
    # cross-reference to its own reference page (turns `create(body=None)` into
    # `create(body: CreateXRequest | None = None)` with CreateXRequest linked).
    for key in (
        "show_signature_annotations: true",
        "separate_signature: true",
        "signature_crossrefs: true",
    ):
        assert key in mk, key
    pp = (tmp_path / "pyproject.toml").read_text()
    assert "griffe-pydantic" in pp


def test_gen_ref_pages_walks_wrapper_resources(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    script = (tmp_path / "docs/scripts/gen_ref_pages.py").read_text()
    # The reference walks the wrapper resources (via _WRAPPERS) + models, NOT the
    # raw api/ classes.
    assert "_WRAPPERS" in script
    assert "extras.resources" in script
    # oneOf wrapper variant-link rendering is preserved for models.
    assert "actual_instance" in script
    assert "One of the following variants" in script
    # the raw api/ subpackage is no longer walked.
    assert 'SUBPACKAGES = ("api", "models")' not in script
    # valid Python after the legacy single-spec render
    ast.parse(script)


def test_gen_ref_pages_federated_loops_subpackages() -> None:
    # A federated distribution (prisma_access) exposes `_SUBPACKAGES` on its
    # top-level package; the script must runtime-detect it and loop the
    # sub-packages, grouping every wrapper + model page under reference/<slug>/.
    script = _render_gen_ref("prisma_access")
    assert 'PACKAGE = "prisma_access"' in script
    # runtime federation detect against the composer registry (not a jinja flag).
    assert "_SUBPACKAGES" in script
    assert 'getattr(pkg, "_SUBPACKAGES", None)' in script
    # federated dispatch: per slug, the dotted sub-package is prisma_access.<slug>
    # and the (slug,) prefix makes nav keys / doc paths reference/<slug>/...
    assert "for slug in subpkgs:" in script
    assert 'f"{PACKAGE}.{slug}"' in script  # -> prisma_access.<slug>.extras/.models
    assert "(slug,)" in script  # nav/path prefix -> reference/<slug>/...
    # single-spec dispatch still present (flat, empty prefix).
    assert "_emit(PACKAGE, src, ())" in script
    # the per-page identifiers are built from the dotted sub-package.
    assert 'f"{dotted_pkg}.extras.resources"' in script
    ast.parse(script)  # valid Python in the federated render


def test_gen_ref_pages_single_spec_byte_identical_modulo_package() -> None:
    # Federation is a RUNTIME detect, so the rendered script is package-agnostic:
    # a federated and a single-spec render differ ONLY in the PACKAGE constant.
    # That pins the legacy single-spec output as byte-identical (the `else:`
    # branch is reached purely by the absence of `_SUBPACKAGES`).
    federated = _render_gen_ref("prisma_access")
    single = _render_gen_ref("prisma_browser")
    ast.parse(single)
    diff = [
        (a, b)
        for a, b in zip(single.splitlines(), federated.splitlines(), strict=True)
        if a != b
    ]
    assert diff == [('PACKAGE = "prisma_browser"', 'PACKAGE = "prisma_access"')]


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


def test_crud_renders_synthesized_body_code(tmp_path: Path) -> None:
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, _ctx())
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "CustomApplicationInput(" in crud
    assert 'name="example"' in crud
    assert "CreateOrReplaceAppInput(...)" not in crud  # no opaque placeholder


def test_crud_uses_manual_override_verbatim(tmp_path: Path) -> None:
    ctx = _ctx()
    ctx["showcase"]["operations"]["create"]["example_override"] = (
        "created = client.application.create(MAGIC)"
    )
    scaffold.render_scaffold(scaffold.builtin_dir(), None, tmp_path, ctx)
    crud = (tmp_path / "docs/guides/crud.md").read_text()
    assert "MAGIC" in crud
    assert 'name="example"' not in crud  # override replaced the whole call


@pytest.mark.skipif(not _SDK.exists(), reason="prisma-browser SDK not built")
def test_docs_context_slots_are_real_wrapper_methods() -> None:
    """The emitted CRUD slots must reference REAL wrapper methods.

    Dispatch-style guard: build the docs context from the REAL built SDK and
    cross-check every slot's clean verb against the wrapper class's actual methods
    in `_WRAPPERS[object]`. A future raw-surface regression (a slot naming a raw
    `*Api` method, or a non-existent verb) fails here.
    """
    import importlib
    import sys

    from phantasos.generator.sdk.docs import build_docs_context
    from phantasos.productconfig import load_product

    loaded = load_product("prisma-browser")
    ctx = build_docs_context(loaded, _SDK)
    showcase: dict[str, Any] = ctx["showcase"]  # type: ignore[assignment]
    obj = showcase["attr"]
    assert obj == "application"  # singular wrapper-object key, not the plural resource

    added = str(_SDK) not in sys.path
    if added:
        sys.path.insert(0, str(_SDK))
    try:
        facade = importlib.import_module("prisma_browser.extras.facade")
        wrapper_cls = facade._WRAPPERS[obj][0]
    finally:
        if added and str(_SDK) in sys.path:
            sys.path.remove(str(_SDK))

    assert obj in facade._WRAPPERS  # the object is a real wrapper key
    for slot, op in showcase["operations"].items():
        verb = op["method"]
        # the slot's method is a genuine, public wrapper method (a clean verb)
        assert callable(getattr(wrapper_cls, verb, None)), (slot, verb)
        assert not verb.startswith("_")
        # and it is NOT a raw *Api method name leaking through
        assert "_by_id" not in verb and "_application" not in verb
