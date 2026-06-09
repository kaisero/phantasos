from pathlib import Path

import pytest

from phantasos.generator.cli.classify import (
    build_cli_ir,
    classify_name,
    detect_id_param,
    fields_to_flags,
    resolve_variants,
)
from phantasos.generator.cli.cliconfig import CliConfig, VariantMap
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.inventory import FieldInfo, OperationInfo, ParamInfo

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


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


def test_build_cli_ir_end_to_end():
    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        }
    )
    ir, unmapped = build_cli_ir(inv, cfg)
    cmds = {(c.verb, c.object, c.variant): c for c in ir.commands}

    # CRUD on widgets
    assert ("set", "widget", None) in cmds
    assert ("show", "widget", None) in cmds
    assert ("del", "widget", None) in cmds

    # set widget has body flags incl. --name
    setw = cmds[("set", "widget", None)]
    assert any(f.name == "--name" for f in setw.body_flags)

    # gizmo create fans out into variant subcommands
    assert ("set", "gizmo", "simple") in cmds
    assert ("set", "gizmo", "complex") in cmds
    complex_cmd = cmds[("set", "gizmo", "complex")]
    assert any(f.name == "--depth" for f in complex_cmd.body_flags)

    # things use a non-literal id param
    show_thing = cmds[("show", "thing", None)]
    assert any(f.kind == "id" and f.param == "thing_id" for f in show_thing.path_params)

    # *_positions is unmapped
    assert "widgets.update_widget_positions" in unmapped

    assert ir.sdk_version == "9.9.9"
