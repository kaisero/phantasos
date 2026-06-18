# tests/test_cli_docs.py
from phantasos.generator.cli.inventory import OperationInfo, ParamInfo
from phantasos.generator.sdk.docs import classify_operations


def _op(method, params):
    return OperationInfo(
        resource="applications", method=method,
        params=[ParamInfo(**p) for p in params],
    )


def _path(name, required=True):
    return {"name": name, "annotation": "str", "location": "path", "required": required}


def _body(name, model):
    return {"name": name, "annotation": model, "location": "body",
            "required": True, "body_model": model}


APPLICATIONS = [
    _op("bulk_create_applications", [_path("type")]),
    _op("create_application", [_path("type"), _body("create_or_replace_app_input", "CreateOrReplaceAppInput")]),
    _op("get_application_by_id", [_path("id")]),
    _op("get_application_by_type_and_id", [_path("type"), _path("id")]),
    _op("list_applications", []),
    _op("list_applications_by_type", [_path("type")]),
    _op("list_application_categories", []),
    _op("patch_application_by_type_and_id", [_path("type"), _path("id"), _body("patch_app_input", "PatchAppInput")]),
    _op("delete_application_by_id", [_path("id")]),
    _op("delete_application_by_type_and_id", [_path("type"), _path("id")]),
    _op("bulk_delete_applications", []),
]


def test_classify_picks_canonical_ops():
    slots = classify_operations(APPLICATIONS, "applications", None)
    assert slots["create"].method == "create_application"
    assert slots["read"].method == "get_application_by_id"
    assert slots["list"].method == "list_applications"
    assert slots["update"].method == "patch_application_by_type_and_id"
    assert slots["delete"].method == "delete_application_by_id"


def test_classify_rejects_different_noun():
    slots = classify_operations(APPLICATIONS, "applications", None)
    # list_application_categories is a different noun -> never chosen for "list"
    assert slots["list"].method != "list_application_categories"


def test_classify_excludes_bulk():
    slots = classify_operations(APPLICATIONS, "applications", None)
    assert not slots["create"].method.startswith("bulk_")


def test_classify_partial_crud_omits_missing(monkeypatch):
    ops = [_op("create_application", [_path("type"), _body("b", "B")]),
           _op("list_applications", [])]
    slots = classify_operations(ops, "applications", None)
    assert set(slots) == {"create", "list"}


def test_classify_honours_override():
    from phantasos.productconfig import DocsOperations
    ov = DocsOperations(read="get_application_by_type_and_id")
    slots = classify_operations(APPLICATIONS, "applications", ov)
    assert slots["read"].method == "get_application_by_type_and_id"


def test_shape_context_shapes_showcase_and_credentials():
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.inventory import OperationInventory
    from phantasos.generator.sdk.docs import shape_context

    inv = OperationInventory(
        sdk_package="prisma_browser", sdk_version="1.0.0", operations=APPLICATIONS
    )
    ctx = shape_context(
        inv, resource="applications", site_name="Demo",
        auth=ScmOAuth(type="scm_oauth"), overrides=None, has_pagination=True,
    )
    assert ctx["has_docs"] is True
    assert ctx["site_name"] == "Demo"
    sc = ctx["showcase"]
    assert sc["attr"] == "applications"
    assert sc["has_create"] and sc["has_list"]
    assert sc["operations"]["create"]["method"] == "create_application"
    # create requires the `type` path arg + the body model
    create_args = sc["operations"]["create"]["required_args"]
    assert any(a["name"] == "type" and a["kind"] == "path" for a in create_args)
    assert any(a["kind"] == "body" and a["body_model"] == "CreateOrReplaceAppInput"
               for a in create_args)
    # credentials come from the auth descriptor
    names = {c["env_var"] for c in ctx["credentials"]}
    assert {"CLIENT_ID", "CLIENT_SECRET", "SCOPE"} <= names


def test_build_docs_context_unknown_resource(tmp_path):
    import pytest
    from phantasos.generator.cli.inventory import OperationInventory
    from phantasos.generator.sdk import docs

    inv = OperationInventory(sdk_package="p", sdk_version="1", operations=APPLICATIONS)
    with pytest.raises(ValueError, match="nope.*applications"):
        docs._validate_resource(inv, "nope")
