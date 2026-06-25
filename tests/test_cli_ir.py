from phantasos.generator.cli.ir import CliIR, Command, Flag, MethodBinding


def test_flag_defaults() -> None:
    f = Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)
    assert f.default is None
    assert f.choices is None
    assert f.help == ""


def test_command_with_bindings_roundtrip() -> None:
    cmd = Command(
        verb="update",
        object="application",
        variant=None,
        key="update:application",
        sdk_resource="applications",
        bindings=[
            MethodBinding(
                sdk_method="patch_application_by_type_and_id",
                sub_verb="patch",
                requires=["type", "id"],
            ),
        ],
        path_params=[
            Flag(name="--id", param="id", py_type="str", kind="id", required=False)
        ],
        body_flags=[
            Flag(
                name="--name", param="name", py_type="str", kind="scalar", required=True
            )
        ],
    )
    ir = CliIR(sdk_package="fakesdk", sdk_version="9.9.9", commands=[cmd])
    assert ir.commands[0].key == "update:application"
    assert [b.sub_verb for b in ir.commands[0].bindings] == ["patch"]
    assert CliIR.model_validate_json(ir.model_dump_json()) == ir


def test_command_columns_roundtrip() -> None:
    from phantasos.generator.cli.ir import CliIR, ColumnSpec, Command

    cmd = Command(
        verb="show",
        object="widget",
        key="show:widget",
        sdk_resource="widgets",
        items_field="data",
        columns=[
            ColumnSpec(header="name", path="name"),
            ColumnSpec(header="OWNER", path="owner.name"),
        ],
    )
    ir = CliIR(sdk_package="x", sdk_version="1", commands=[cmd])
    back = CliIR.model_validate_json(ir.model_dump_json())
    assert back.commands[0].items_field == "data"
    assert back.commands[0].columns[1].path == "owner.name"


def test_flag_cli_default_roundtrip() -> None:
    from phantasos.generator.cli.ir import Flag

    f = Flag(
        name="--sort",
        param="sort",
        py_type="str",
        kind="enum",
        required=False,
        cli_default="application.id",
    )
    back = Flag.model_validate_json(f.model_dump_json())
    assert back.cli_default == "application.id"
    assert back.default is None  # SDK/model default stays separate


def test_model_registry_roundtrips() -> None:
    from phantasos.generator.cli.ir import CliIR, ModelField, ModelSchema

    ir = CliIR(
        sdk_package="x",
        sdk_version="1",
        models={
            "Saas": ModelSchema(
                fields=[
                    ModelField(
                        name="access_mode",
                        alias="accessMode",
                        py_type="str",
                        kind="enum",
                        required=True,
                        enum_values=["none", "any"],
                    ),
                    ModelField(
                        name="specific",
                        alias="specific",
                        py_type="Specific | None",
                        kind="json",
                        required=False,
                        model_ref="Specific",
                    ),
                ]
            )
        },
    )
    back = CliIR.model_validate_json(ir.model_dump_json())
    assert back.models["Saas"].fields[1].model_ref == "Specific"
    assert back.models["Saas"].fields[0].enum_values == ["none", "any"]


def test_flag_carries_model_ref() -> None:
    from phantasos.generator.cli.ir import Flag

    f = Flag(
        name="--applications",
        param="applications",
        py_type="str",
        kind="json",
        required=False,
        model_ref="AccessAndDataPostApplications",
    )
    assert f.model_ref == "AccessAndDataPostApplications"
