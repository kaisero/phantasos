# tests/test_cli_introspect.py
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.inventory import OperationInfo, OperationInventory

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.fixture
def inv() -> OperationInventory:
    return introspect("fakesdk", FIXTURE)


def _op(inv: OperationInventory, resource: str, method: str) -> OperationInfo:
    return next(
        o for o in inv.operations if o.resource == resource and o.method == method
    )


def test_version_and_resources(inv: OperationInventory) -> None:
    assert inv.sdk_package == "fakesdk"
    assert inv.sdk_version == "9.9.9"
    assert {o.resource for o in inv.operations} == {"widgets", "gizmos", "things"}


def test_excludes_http_info_and_serialize(inv: OperationInventory) -> None:
    methods = {o.method for o in inv.operations if o.resource == "widgets"}
    assert "create_widget" in methods
    assert "create_widget_with_http_info" not in methods
    assert "_create_widget_serialize" not in methods


def test_path_and_body_params(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "create_widget")
    body = [p for p in op.params if p.location == "body"]
    assert body and body[0].name == "widget_input"
    assert body[0].body_model == "WidgetInput"
    assert op.summary == "Create a widget."


def test_enum_param_values(inv: OperationInventory) -> None:
    op = _op(inv, "gizmos", "create_gizmo")
    type_param = next(p for p in op.params if p.name == "type")
    assert type_param.location == "path"
    assert type_param.enum_values == ["simple", "complex"]


def test_union_body_members(inv: OperationInventory) -> None:
    op = _op(inv, "gizmos", "create_gizmo")
    body = next(p for p in op.params if p.location == "body")
    assert body.union_members == ["SimpleGizmoInput", "ComplexGizmoInput"]


def test_body_fields_recursed(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "create_widget")
    fields = op.body_fields["WidgetInput"]
    by_name = {f.name: f for f in fields}
    assert by_name["name"].kind == "scalar" and by_name["name"].required
    assert by_name["color"].kind == "enum" and by_name["color"].enum_values == [
        "red",
        "blue",
    ]
    assert by_name["spec"].kind == "json"


def test_sys_path_restored_after_introspect() -> None:
    before = list(sys.path)
    introspect("fakesdk", FIXTURE)
    # introspect must not leave the SDK path lingering on sys.path
    assert sys.path == before


def test_literal_field_is_enum(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "create_widget")
    fields = {f.name: f for f in op.body_fields["WidgetInput"]}
    assert fields["mode"].kind == "enum"
    assert fields["mode"].enum_values == ["fast", "slow"]


def test_path_param_description_captured(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "get_widget_by_id")
    id_param = next(p for p in op.params if p.name == "id")
    assert id_param.description == "The widget id."


def test_response_capture_list_envelope(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "list_widgets")
    assert op.return_model == "WidgetList"
    assert op.items_field == "data"
    names = [f.name for f in op.response_fields]
    assert "id" in names and "name" in names  # item (Widget) fields, not envelope's


def test_response_capture_get_returns_item_directly(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "get_widget_by_id")
    assert op.return_model == "Widget"
    assert op.items_field is None
    kinds = {f.name: f.kind for f in op.response_fields}
    assert kinds["spec"] == "json"  # nested dict
    assert kinds["tags"] == "scalar"  # list[str] counts as scalar kind


def test_response_capture_absent_when_unannotated(inv: OperationInventory) -> None:
    op = _op(inv, "gizmos", "list_gizmos")
    assert op.return_model is None
    assert op.items_field is None
    assert op.response_fields == []


def test_response_capture_divergent_create_model(inv: OperationInventory) -> None:
    op = _op(inv, "widgets", "create_widget")
    assert op.return_model == "CreateWidget201Response"
    assert [f.name for f in op.response_fields] == ["widget_id"]


def test_list_field_not_named_data_is_not_an_envelope() -> None:
    """A model containing list[Model] under any other name (e.g. a real item like
    User.user_groups) is the ITEM, not a list envelope."""
    from pydantic import BaseModel

    from phantasos.generator.cli.introspect import _response_info

    class Member(BaseModel):
        name: str

    class Team(BaseModel):  # item model that HAPPENS to contain a list[Model]
        id: str
        members: list[Member] = []

    model, items_field, fields = _response_info(Team)
    assert model == "Team"
    assert items_field is None  # NOT mistaken for an envelope
    assert [f.name for f in fields] == ["id", "members"]


def test_public_primitives_exported() -> None:
    # Submodule-direct import — EXACTLY what cli/modelschema.py (Task 4) uses.
    # Do NOT use `from ...opmodel import introspect as I`: opmodel/__init__.py does
    # `from .introspect import introspect`, rebinding the package attribute
    # `opmodel.introspect` to the FUNCTION (shadowing the submodule), so `I.field_kind`
    # would raise AttributeError. The submodule path below is the real contract.
    from phantasos.generator.opmodel.introspect import (
        enum_values,
        field_kind,
        scalar_type,
        union_members,
        unwrap_optional,
    )

    assert field_kind(str) == "scalar"
    assert field_kind(list[str]) == "scalar"
    assert unwrap_optional(str | None) is str
    assert enum_values(int) is None
    assert scalar_type(bool) == "bool"
    assert callable(union_members)
