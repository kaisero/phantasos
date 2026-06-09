# tests/test_cli_introspect.py
from pathlib import Path

import pytest

from phantasos.generator.cli.introspect import introspect

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.fixture
def inv():
    return introspect("fakesdk", FIXTURE)


def _op(inv, resource, method):
    return next(o for o in inv.operations if o.resource == resource and o.method == method)


def test_version_and_resources(inv):
    assert inv.sdk_package == "fakesdk"
    assert inv.sdk_version == "9.9.9"
    assert {o.resource for o in inv.operations} == {"widgets", "gizmos", "things"}


def test_excludes_http_info_and_serialize(inv):
    methods = {o.method for o in inv.operations if o.resource == "widgets"}
    assert "create_widget" in methods
    assert "create_widget_with_http_info" not in methods
    assert "_create_widget_serialize" not in methods


def test_path_and_body_params(inv):
    op = _op(inv, "widgets", "create_widget")
    body = [p for p in op.params if p.location == "body"]
    assert body and body[0].name == "widget_input"
    assert body[0].body_model == "WidgetInput"
    assert op.summary == "Create a widget."


def test_enum_param_values(inv):
    op = _op(inv, "gizmos", "create_gizmo")
    type_param = next(p for p in op.params if p.name == "type")
    assert type_param.location == "path"
    assert type_param.enum_values == ["simple", "complex"]


def test_union_body_members(inv):
    op = _op(inv, "gizmos", "create_gizmo")
    body = next(p for p in op.params if p.location == "body")
    assert body.union_members == ["SimpleGizmoInput", "ComplexGizmoInput"]


def test_body_fields_recursed(inv):
    op = _op(inv, "widgets", "create_widget")
    fields = op.body_fields["WidgetInput"]
    by_name = {f.name: f for f in fields}
    assert by_name["name"].kind == "scalar" and by_name["name"].required
    assert by_name["color"].kind == "enum" and by_name["color"].enum_values == ["red", "blue"]
    assert by_name["spec"].kind == "json"
