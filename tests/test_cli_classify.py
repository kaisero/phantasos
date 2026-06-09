import pytest

from phantasos.generator.cli.classify import (
    classify_name,
    detect_id_param,
    fields_to_flags,
    resolve_variants,
)
from phantasos.generator.cli.cliconfig import VariantMap
from phantasos.generator.cli.inventory import FieldInfo, OperationInfo, ParamInfo


@pytest.mark.parametrize(
    "method,verb,obj",
    [
        ("create_application", "set", "application"),
        ("patch_application_by_type_and_id", "set", "application"),
        ("update_device_group", "set", "device-group"),
        ("delete_application_by_id", "del", "application"),
        ("bulk_delete_applications", "del", "application"),
        ("get_application_by_id", "show", "application"),
        ("list_applications", "show", "application"),
        ("list_device_groups", "show", "device-group"),
        ("bulk_create_applications", "set", "application"),
        ("create_access_and_data_rule", "set", "access-and-data-rule"),
    ],
)
def test_classify_verb_and_noun(method, verb, obj):
    c = classify_name(method)
    assert c is not None
    assert (c.verb, c.object) == (verb, obj)


@pytest.mark.parametrize(
    "method",
    [
        "update_access_and_data_positions",  # reorder, not a "position" object
        "force_reauth_devices",
        "suspend_users",
        "revoke_user_request",
        "publish_draft_configuration",
        "action_user_request",
    ],
)
def test_unmapped_returns_none(method):
    assert classify_name(method) is None


def _p(name, location, required=True, enum_values=None):
    return ParamInfo(name=name, annotation="str", location=location,
                     required=required, enum_values=enum_values)


def test_detect_id_literal():
    params = [_p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_nonliteral_name():
    params = [_p("thing_id", "path")]
    assert detect_id_param(params).name == "thing_id"


def test_detect_id_ignores_discriminator_enum():
    # type is a path enum (discriminator), id is the real id
    params = [_p("type", "path", enum_values=["simple", "complex"]), _p("id", "path")]
    assert detect_id_param(params).name == "id"


def test_detect_id_none_when_no_path_id():
    params = [_p("name", "query", required=False)]
    assert detect_id_param(params) is None


def test_fields_to_flags_kinds():
    fields = [
        FieldInfo(name="name", annotation="str", kind="scalar", required=True),
        FieldInfo(name="color", annotation="Color", kind="enum", required=False,
                  enum_values=["red", "blue"]),
        FieldInfo(name="spec", annotation="dict", kind="json", required=False),
    ]
    flags = {f.param: f for f in fields_to_flags(fields)}
    assert flags["name"].name == "--name" and flags["name"].required
    # enum stays permissive: kind == enum, choices populated, but py_type is str
    assert flags["color"].kind == "enum"
    assert flags["color"].choices == ["red", "blue"]
    assert flags["color"].py_type == "str"
    assert flags["spec"].kind == "json"


def test_snake_case_field_becomes_kebab_flag():
    fields = [
        FieldInfo(name="ip_netmask", annotation="str", kind="scalar", required=True)
    ]
    assert fields_to_flags(fields)[0].name == "--ip-netmask"


def test_resolve_variants_from_config():
    op = OperationInfo(
        resource="gizmos", method="create_gizmo",
        params=[
            ParamInfo(name="type", annotation="WidgetType", location="path",
                      required=True, enum_values=["simple", "complex"]),
            ParamInfo(name="create_gizmo_input", annotation="CreateGizmoInput",
                      location="body", required=True, body_model="CreateGizmoInput",
                      union_members=["SimpleGizmoInput", "ComplexGizmoInput"]),
        ],
        body_fields={
            "SimpleGizmoInput": [
                FieldInfo(name="name", annotation="str", kind="scalar", required=True),
            ],
            "ComplexGizmoInput": [
                FieldInfo(name="name", annotation="str", kind="scalar", required=True),
                FieldInfo(name="depth", annotation="int", kind="scalar", required=True),
            ],
        },
    )
    vmap = VariantMap(
        path_param="type",
        map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
    )
    variants = resolve_variants(op, vmap)
    assert [v.name for v in variants] == ["simple", "complex"]
    assert variants[1].model == "ComplexGizmoInput"


def test_resolve_variants_none_without_config():
    op = OperationInfo(resource="widgets", method="create_widget")
    assert resolve_variants(op, None) == []
