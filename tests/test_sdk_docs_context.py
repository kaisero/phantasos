# tests/test_sdk_docs_context.py
"""Unit tests for the WRAPPER-driven docs context (generator.sdk.docs).

The docs context is built from the SDK's typed wrappers (`cli_operations`, which
stamps each op with `object_attr`/`clean_method`/`has_body`). `classify_operations`
reads the clean verbs directly — no raw-prefix verb heuristic. These tests feed
wrapper-stamped `OperationInfo`s and assert the showcase slots are the clean verbs
on the object, with the body under the `body` kwarg.
"""

from typing import Any

import pytest

from phantasos.generator.cli.inventory import (
    OperationInfo,
    OperationInventory,
    ParamInfo,
)
from phantasos.generator.sdk.docs import classify_operations


def _op(
    raw_method: str,
    clean_method: str,
    params: list[dict[str, Any]],
    *,
    obj: str = "application",
    has_body: bool = False,
) -> OperationInfo:
    """A wrapper-stamped op, as `cli_operations` would emit it."""
    return OperationInfo(
        resource="applications",
        method=raw_method,
        params=[ParamInfo(**p) for p in params],
        object_attr=obj,
        clean_method=clean_method,
        has_body=has_body,
    )


def _path(name: str, required: bool = True) -> dict[str, Any]:
    return {"name": name, "annotation": "str", "location": "path", "required": required}


def _body(name: str, model: str) -> dict[str, Any]:
    return {
        "name": name,
        "annotation": model,
        "location": "body",
        "required": True,
        "body_model": model,
    }


# The wrapper view of the application object: clean verbs, multi-binding get/list/
# delete (id-only vs type+id). `cli_operations` emits one op per binding.
APPLICATION = [
    _op(
        "create_application",
        "create",
        [_path("type"), _body("b", "CreateApp")],
        has_body=True,
    ),
    _op("get_application_by_id", "get", [_path("id")]),
    _op("get_application_by_type_and_id", "get", [_path("type"), _path("id")]),
    _op("list_applications", "list", []),
    _op("list_applications_by_type", "list", [_path("type")]),
    _op(
        "patch_application_by_type_and_id",
        "update",
        [_path("type"), _path("id"), _body("b", "PatchApp")],
        has_body=True,
    ),
    _op("delete_application_by_id", "delete", [_path("id")]),
    _op("delete_application_by_type_and_id", "delete", [_path("type"), _path("id")]),
    # bulk_create/bulk_delete are clean verbs `bulk_create`/`bulk_delete`, NOT CRUD
    # slots — they must never populate create/delete.
    _op("bulk_create_applications", "bulk_create", [_path("type")]),
    _op("bulk_delete_applications", "bulk_delete", []),
    # a different object backed by the same api class: must be ignored for `application`
    _op("list_application_categories", "list", [], obj="application_category"),
]


def test_classify_maps_clean_verbs_to_slots() -> None:
    slots = classify_operations(APPLICATION, "application")
    assert slots["create"].clean_method == "create"
    assert slots["read"].clean_method == "get"
    assert slots["list"].clean_method == "list"
    assert slots["update"].clean_method == "update"
    assert slots["delete"].clean_method == "delete"


def test_classify_picks_fewest_path_params_binding() -> None:
    slots = classify_operations(APPLICATION, "application")
    # get/list/delete each have an id-only and a type+id binding; the minimal one wins
    assert slots["read"].method == "get_application_by_id"
    assert slots["list"].method == "list_applications"
    assert slots["delete"].method == "delete_application_by_id"


def test_classify_ignores_non_crud_verbs() -> None:
    slots = classify_operations(APPLICATION, "application")
    # bulk_create/bulk_delete are not create/delete slots
    assert slots["create"].clean_method == "create"
    assert slots["delete"].clean_method == "delete"
    assert "bulk_create" not in slots and "bulk_delete" not in slots


def test_classify_ignores_other_objects() -> None:
    slots = classify_operations(APPLICATION, "application")
    # list_application_categories belongs to application_category, not application
    assert slots["list"].method == "list_applications"


def test_classify_partial_crud_omits_missing() -> None:
    ops = [
        _op(
            "create_application",
            "create",
            [_path("type"), _body("b", "B")],
            has_body=True,
        ),
        _op("list_applications", "list", []),
    ]
    slots = classify_operations(ops, "application")
    assert set(slots) == {"create", "list"}


def test_shape_context_shapes_wrapper_showcase_and_credentials() -> None:
    from phantasos.config import ScmOAuth
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(sdk_package="prisma_browser", sdk_version="1.0.0", operations=APPLICATION)
    ctx: dict[str, Any] = shape_context(
        inv,
        obj="application",
        site_name="Demo",
        auth=ScmOAuth(type="scm_oauth"),
        has_pagination=True,
    )
    assert ctx["has_docs"] is True
    assert ctx["site_name"] == "Demo"
    sc: dict[str, Any] = ctx["showcase"]
    # the showcase attr is the SINGULAR object (client.<object>), not the resource
    assert sc["attr"] == "application"
    assert sc["has_create"] and sc["has_list"]
    # the slot method is the CLEAN verb, not the raw method
    assert sc["operations"]["create"]["method"] == "create"
    # create requires the `type` path arg + the body under the `body` kwarg
    create_args: list[dict[str, Any]] = sc["operations"]["create"]["required_args"]
    assert any(a["name"] == "type" and a["kind"] == "path" for a in create_args)
    body = next(a for a in create_args if a["kind"] == "body")
    assert body["name"] == "body"  # wrapper body kwarg, not the raw body-param name
    assert body["body_model"] == "CreateApp"
    # credentials come from the auth descriptor
    creds: list[dict[str, Any]] = ctx["credentials"]
    names = {c["env_var"] for c in creds}
    assert {"CLIENT_ID", "CLIENT_SECRET", "SCOPE"} <= names


def test_build_docs_context_unknown_object_fails_fast() -> None:
    from phantasos.generator.sdk import docs

    with pytest.raises(ValueError, match=r"nope.*application"):
        docs._validate_object(["application", "device"], "nope")


def test_shape_context_synthesizes_body_code_and_override() -> None:
    import datetime

    from pydantic import BaseModel, Field, StrictStr

    from phantasos.generator.sdk.docs import shape_context
    from phantasos.productconfig import DocsExamples

    class AppInput(BaseModel):
        name: StrictStr = Field(description="Name")
        created_at: datetime.datetime

    inv = OperationInventory(
        sdk_package="p",
        sdk_version="1",
        operations=[
            _op(
                "create_app",
                "create",
                [_body("body", "AppInput")],
                obj="app",
                has_body=True,
            )
        ],
    )
    ctx: dict[str, Any] = shape_context(
        inv,
        obj="app",
        site_name="x",
        auth=None,
        has_pagination=False,
        resolve={"AppInput": AppInput}.get,
        variant=None,
        examples=DocsExamples(create="X = 1"),
    )
    op = ctx["showcase"]["operations"]["create"]
    body = next(a for a in op["required_args"] if a["kind"] == "body")
    assert body["body_code"].startswith("AppInput(")
    assert 'name="example"' in body["body_code"]
    assert op["example_override"] == "X = 1"


def test_shape_context_falls_back_without_resolver() -> None:
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(
        sdk_package="p",
        sdk_version="1",
        operations=[
            _op(
                "create_app",
                "create",
                [_body("body", "AppInput")],
                obj="app",
                has_body=True,
            )
        ],
    )
    ctx: dict[str, Any] = shape_context(
        inv,
        obj="app",
        site_name="x",
        auth=None,
        has_pagination=False,
    )
    body = next(a for a in ctx["showcase"]["operations"]["create"]["required_args"] if a["kind"] == "body")
    assert body["body_code"] == "AppInput(...)"


def test_shape_context_call_path_prefixes_subpackage() -> None:
    """Federated: call path is `<sub>.<object>` while `attr` stays a clean id."""
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(sdk_package="prisma_access", sdk_version="1", operations=APPLICATION)
    ctx: dict[str, Any] = shape_context(
        inv,
        obj="application",
        site_name="x",
        auth=None,
        has_pagination=False,
        subpackage="objects",
    )
    sc: dict[str, Any] = ctx["showcase"]
    # `attr` remains the clean object identifier; `call_path` carries the sub-package
    assert sc["attr"] == "application"
    assert sc["call_path"] == "objects.application"


def test_shape_context_call_path_is_bare_object_when_no_subpackage() -> None:
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(sdk_package="prisma_browser", sdk_version="1", operations=APPLICATION)
    ctx: dict[str, Any] = shape_context(inv, obj="application", site_name="x", auth=None, has_pagination=False)
    sc: dict[str, Any] = ctx["showcase"]
    assert sc["attr"] == "application"
    assert sc["call_path"] == "application"  # single-spec: no prefix


def _loaded_for_docs(package: str, sub: str | None) -> Any:
    from pathlib import Path

    from phantasos.productconfig import DocsConfig, LoadedProduct, ProductConfig

    cfg = ProductConfig(
        package=package,
        output="out",
        base_url="https://example.test",
        docs=DocsConfig(showcase_resource="address", showcase_subpackage=sub),
    )
    return LoadedProduct(
        config=cfg,
        base_dir=Path("/x"),
        spec_path=None,
        output_dir=Path("/x/out"),
        auth=None,
        pagination=None,
        errors=None,
        facade=None,
        retry=None,
        context={"distribution": "dist"},
    )


def _patch_docs_collaborators(monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]) -> None:
    import importlib

    from phantasos.generator.cli import classify as classify_mod
    from phantasos.generator.sdk import docs

    list_op = _op("list_addresses", "list", [], obj="address")

    def fake_wrapper_objects(package: str, project_dir: Any) -> list[str]:
        captured["wrapper_pkg"] = package
        return ["address"]

    def fake_cli_operations(package: str, sdk_path: Any, **_: Any) -> OperationInventory:
        captured["cli_pkg"] = package
        return OperationInventory(sdk_package=package, sdk_version="1", operations=[list_op])

    real_import = importlib.import_module

    def fake_import(name: str, *a: Any, **k: Any) -> Any:
        if name.endswith(".models"):
            captured["models_pkg"] = name
            import types

            return types.ModuleType("models")
        return real_import(name, *a, **k)

    monkeypatch.setattr(docs, "_wrapper_objects", fake_wrapper_objects)
    monkeypatch.setattr(classify_mod, "cli_operations", fake_cli_operations)
    monkeypatch.setattr(importlib, "import_module", fake_import)


def test_build_docs_context_targets_showcase_subpackage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    from phantasos.generator.sdk import docs

    captured: dict[str, Any] = {}
    _patch_docs_collaborators(monkeypatch, captured)
    ctx: dict[str, Any] = docs.build_docs_context(_loaded_for_docs("prisma_access", "objects"), Path("/x"))
    assert captured["wrapper_pkg"] == "prisma_access.objects"
    assert captured["cli_pkg"] == "prisma_access.objects"
    assert captured["models_pkg"] == "prisma_access.objects.models"
    # the guide will render `client.objects.address.<verb>`
    assert ctx["showcase"]["call_path"] == "objects.address"
    assert ctx["showcase"]["attr"] == "address"


def test_build_docs_context_single_spec_targets_root_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    from phantasos.generator.sdk import docs

    captured: dict[str, Any] = {}
    _patch_docs_collaborators(monkeypatch, captured)
    ctx: dict[str, Any] = docs.build_docs_context(_loaded_for_docs("prisma_browser", None), Path("/x"))
    # single-spec targeting is unchanged: root package, bare call path
    assert captured["wrapper_pkg"] == "prisma_browser"
    assert captured["cli_pkg"] == "prisma_browser"
    assert captured["models_pkg"] == "prisma_browser.models"
    assert ctx["showcase"]["call_path"] == "address"
    assert ctx["showcase"]["attr"] == "address"
