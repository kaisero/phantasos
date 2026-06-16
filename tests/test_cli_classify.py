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
from phantasos.generator.cli.inventory import (
    FieldInfo,
    Location,
    OperationInfo,
    ParamInfo,
)

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.mark.parametrize(
    "method,verb,obj",
    [
        ("create_application", "create", "application"),
        ("patch_application_by_type_and_id", "update", "application"),
        ("delete_application_by_id", "delete", "application"),
        ("get_application_by_id", "show", "application"),
        ("list_applications", "show", "application"),
        ("list_device_groups", "show", "device-group"),
        ("create_access_and_data_rule", "create", "access-and-data-rule"),
    ],
)
def test_classify_verb_and_noun(method: str, verb: str, obj: str) -> None:
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
        # PUT (update_*) + bulk_* are deferred — now unmapped
        "update_device_group",
        "bulk_create_applications",
        "bulk_delete_applications",
    ],
)
def test_unmapped_returns_none(method: str) -> None:
    assert classify_name(method) is None


def _p(
    name: str,
    location: Location,
    required: bool = True,
    enum_values: list[str] | None = None,
) -> ParamInfo:
    return ParamInfo(
        name=name,
        annotation="str",
        location=location,
        required=required,
        enum_values=enum_values,
    )


def test_detect_id_literal() -> None:
    params = [_p("id", "path")]
    result = detect_id_param(params)
    assert result is not None
    assert result.name == "id"


def test_detect_id_nonliteral_name() -> None:
    params = [_p("thing_id", "path")]
    result = detect_id_param(params)
    assert result is not None
    assert result.name == "thing_id"


def test_detect_id_ignores_discriminator_enum() -> None:
    # type is a path enum (discriminator), id is the real id
    params = [_p("type", "path", enum_values=["simple", "complex"]), _p("id", "path")]
    result = detect_id_param(params)
    assert result is not None
    assert result.name == "id"


def test_detect_id_none_when_no_path_id() -> None:
    params = [_p("name", "query", required=False)]
    assert detect_id_param(params) is None


def test_fields_to_flags_kinds() -> None:
    fields = [
        FieldInfo(name="name", annotation="str", kind="scalar", required=True),
        FieldInfo(
            name="color",
            annotation="Color",
            kind="enum",
            required=False,
            enum_values=["red", "blue"],
        ),
        FieldInfo(name="spec", annotation="dict", kind="json", required=False),
    ]
    flags = {f.param: f for f in fields_to_flags(fields)}
    assert flags["name"].name == "--name" and flags["name"].required
    # enum stays permissive: kind == enum, choices populated, but py_type is str
    assert flags["color"].kind == "enum"
    assert flags["color"].choices == ["red", "blue"]
    assert flags["color"].py_type == "str"
    assert flags["spec"].kind == "json"


def test_snake_case_field_becomes_kebab_flag() -> None:
    fields = [
        FieldInfo(name="ip_netmask", annotation="str", kind="scalar", required=True)
    ]
    assert fields_to_flags(fields)[0].name == "--ip-netmask"


def test_resolve_variants_from_config() -> None:
    op = OperationInfo(
        resource="gizmos",
        method="create_gizmo",
        params=[
            ParamInfo(
                name="type",
                annotation="WidgetType",
                location="path",
                required=True,
                enum_values=["simple", "complex"],
            ),
            ParamInfo(
                name="create_gizmo_input",
                annotation="CreateGizmoInput",
                location="body",
                required=True,
                body_model="CreateGizmoInput",
                union_members=["SimpleGizmoInput", "ComplexGizmoInput"],
            ),
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


def test_resolve_variants_none_without_config() -> None:
    op = OperationInfo(resource="widgets", method="create_widget")
    assert resolve_variants(op, None) == []


def test_build_cli_ir_end_to_end() -> None:
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
    by_key = {c.key: c for c in ir.commands}

    # CRUD on widgets
    assert "create:widget" in by_key
    assert "update:widget" in by_key
    assert "show:widget" in by_key
    assert "delete:widget" in by_key

    # create widget has body flags incl. --name
    assert any(f.name == "--name" for f in by_key["create:widget"].body_flags)

    # gizmo create fans out into variant subcommands
    assert "create:gizmo:simple" in by_key
    assert "create:gizmo:complex" in by_key
    assert any(f.name == "--depth" for f in by_key["create:gizmo:complex"].body_flags)

    # things use a non-literal id param
    assert any(f.kind == "id" for f in by_key["show:thing"].path_params)

    # *_positions is unmapped
    assert "widgets.update_widget_positions" in unmapped

    assert ir.sdk_version == "9.9.9"


@pytest.mark.parametrize(
    "method,sub_verb",
    [
        ("create_application", "create"),
        ("patch_application_by_type_and_id", "patch"),
        ("get_application_by_id", "get"),
        ("list_applications", "list"),
        ("delete_application_by_id", "delete"),
    ],
)
def test_classify_sub_verb(method: str, sub_verb: str) -> None:
    c = classify_name(method)
    assert c is not None
    assert c.sub_verb == sub_verb


def test_build_cli_ir_aggregates_methods() -> None:
    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        }
    )
    ir, _unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    show_widget = by_key["show:widget"]
    assert {b.sub_verb for b in show_widget.bindings} == {"get", "list"}
    assert show_widget.paginated is True

    # create/update are now single-binding (PUT update_widget is deferred/unmapped)
    create_widget = by_key["create:widget"]
    assert {b.sub_verb for b in create_widget.bindings} == {"create"}
    assert len(create_widget.bindings) == 1
    assert len([c for c in ir.commands if c.key == "create:widget"]) == 1
    update_widget = by_key["update:widget"]
    assert {b.sub_verb for b in update_widget.bindings} == {"patch"}
    assert len(update_widget.bindings) == 1

    show_gizmo = by_key["show:gizmo"]
    pp = {f.param for f in show_gizmo.path_params}
    assert "id" in pp and "type" in pp

    assert "create:gizmo:simple" in by_key
    assert "create:gizmo:complex" in by_key
    assert any(f.name == "--depth" for f in by_key["create:gizmo:complex"].body_flags)

    get_one = next(b for b in show_widget.bindings if b.sub_verb == "get")
    assert get_one.requires == ["id"]
    list_all = next(b for b in show_widget.bindings if b.sub_verb == "list")
    assert list_all.requires == []


def test_bindings_carry_body_and_variant_metadata() -> None:
    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        }
    )
    ir, _ = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    # plain body: build the param's model, no wrapper
    create_widget = next(
        b for b in by_key["create:widget"].bindings if b.sub_verb == "create"
    )
    assert create_widget.body_param == "widget_input"
    assert create_widget.body_model == "WidgetInput"
    assert create_widget.body_wrapper is None

    # variant body: build the VARIANT model, wrap in the param's wrapper model
    simple = by_key["create:gizmo:simple"].bindings[0]
    assert simple.body_model == "SimpleGizmoInput"
    assert simple.body_wrapper == "CreateGizmoInput"

    # variant_param recorded; facade_module set
    assert by_key["create:gizmo:simple"].variant_param == "type"
    assert by_key["create:widget"].variant_param is None
    assert ir.facade_module == "fakesdk.extras.facade"


def test_fixture_client_from_env_and_wrapper() -> None:
    # the fixture mirrors the real facade Client + positional-wrapper construction
    import sys

    sys.path.insert(0, str(FIXTURE))
    try:
        from fakesdk.extras.facade import Client
        from fakesdk.models import CreateGizmoInput, SimpleGizmoInput

        c = Client.from_env()
        assert hasattr(c, "widgets") and hasattr(c, "paginate")
        wrapped = CreateGizmoInput(SimpleGizmoInput(name="x"))
        assert isinstance(wrapped.actual_instance, SimpleGizmoInput)
    finally:
        sys.path.remove(str(FIXTURE))


def test_query_int_flag_has_int_py_type() -> None:
    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, CliConfig())
    show_widget = next(c for c in ir.commands if c.key == "show:widget")
    limit = next(f for f in show_widget.query_flags if f.param == "limit")
    assert limit.py_type == "int"
    name = next(f for f in show_widget.query_flags if f.param == "name")
    assert name.py_type == "str"


def test_build_cli_ir_emits_request_commands() -> None:
    from phantasos.generator.cli.cliconfig import RequestMapping

    inv = introspect("fakesdk", FIXTURE)
    cfg = CliConfig(
        request={
            "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
            "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
        }
    )
    ir, unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    assert "request:widget:suspend" in by_key
    assert "request:widget:revoke" in by_key
    susp = by_key["request:widget:suspend"]
    assert susp.verb == "request" and susp.object == "widget"
    assert susp.action == "suspend"  # dedicated action field
    assert susp.variant is None and susp.variant_param is None  # NOT a oneOf variant
    assert [b.sub_verb for b in susp.bindings] == ["action"]
    assert susp.bindings[0].sdk_method == "suspend_widget"
    # body-only action: body flags from the model, no --id
    assert any(f.name == "--name" for f in susp.body_flags)
    assert not any(f.kind == "id" for f in susp.path_params)
    # id+body action: --id present
    rev = by_key["request:widget:revoke"]
    assert any(f.kind == "id" for f in rev.path_params)
    assert rev.bindings[0].sdk_method == "revoke_widget"
    assert "widgets.suspend_widget" not in unmapped
    assert "widgets.revoke_widget" not in unmapped
    # all command keys are distinct (no request/CRUD collision)
    keys = [c.key for c in ir.commands]
    assert len(keys) == len(set(keys))


def test_show_widget_gets_default_columns_and_items_field() -> None:
    from pathlib import Path

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    ir, _ = build_cli_ir(introspect("fakesdk", fixture), CliConfig())
    show = next(c for c in ir.commands if c.key == "show:widget")
    assert show.items_field == "data"  # from list_widgets -> WidgetList
    paths = [c.path for c in show.columns]
    assert paths[:2] == ["id", "name"]  # preferred first
    assert "spec" not in paths  # nested excluded
    create = next(c for c in ir.commands if c.key == "create:widget")
    assert [c.path for c in create.columns] == paths  # same object, same columns


def test_cli_yml_columns_override_and_validate() -> None:
    from pathlib import Path

    import pytest

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)

    cfg = CliConfig(columns={"widget": ["name", "members[].name"]})
    ir, _ = build_cli_ir(inv, cfg)
    show = next(c for c in ir.commands if c.key == "show:widget")
    assert [c.path for c in show.columns] == ["name", "members[].name"]
    # curated columns validate against the SHOW item model and attach to every
    # command of the object — even though create_widget returns the divergent
    # CreateWidget201Response{widget_id} (no `name` field), the build must pass:
    create = next(c for c in ir.commands if c.key == "create:widget")
    assert [c.path for c in create.columns] == ["name", "members[].name"]

    with pytest.raises(ValueError, match="unknown field 'nope'"):
        build_cli_ir(inv, CliConfig(columns={"widget": ["nope"]}))

    with pytest.raises(ValueError, match="unknown object"):
        build_cli_ir(inv, CliConfig(columns={"no-such-object": ["id"]}))


def test_no_response_model_means_no_columns() -> None:
    from pathlib import Path

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    ir, _ = build_cli_ir(introspect("fakesdk", fixture), CliConfig())
    gizmo_show = next(c for c in ir.commands if c.key == "show:gizmo")
    assert gizmo_show.columns == []  # gizmos are unannotated
    assert gizmo_show.items_field is None


def test_defaults_stamp_cli_default_on_query_flags() -> None:
    from pathlib import Path

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)
    cfg = CliConfig(
        defaults={
            "widgets.list_widgets": {"name": "gadget", "limit": 50},
        }
    )
    ir, _ = build_cli_ir(inv, cfg)
    show = next(c for c in ir.commands if c.key == "show:widget")
    by_param = {f.param: f for f in show.query_flags}
    assert by_param["name"].cli_default == "gadget"  # str preserved
    assert by_param["limit"].cli_default == 50  # int preserved
    # untouched flags stay None; body flags never gain cli_default
    assert all(f.cli_default is None for f in show.body_flags)
    create = next(c for c in ir.commands if c.key == "create:widget")
    assert all(f.cli_default is None for f in create.body_flags)


def test_get_by_id_only_flag() -> None:
    """`thing` exposes only get_thing(thing_id) (no list) -> get_by_id_only;
    `widget` has list_widgets -> not id-only."""
    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, CliConfig())
    by_key = {c.key: c for c in ir.commands}
    assert by_key["show:thing"].get_by_id_only is True
    assert by_key["show:widget"].get_by_id_only is False


def test_defaults_validation_errors() -> None:
    from pathlib import Path

    import pytest

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    inv = introspect("fakesdk", fixture)

    with pytest.raises(ValueError, match="unknown operation"):
        build_cli_ir(inv, CliConfig(defaults={"widgets.no_such_op": {"limit": 1}}))

    with pytest.raises(ValueError, match="not a query param"):
        build_cli_ir(inv, CliConfig(defaults={"widgets.list_widgets": {"bogus": "x"}}))
