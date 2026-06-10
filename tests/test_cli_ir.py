from phantasos.generator.cli.ir import CliIR, Command, Flag, MethodBinding


def test_flag_defaults():
    f = Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)
    assert f.default is None
    assert f.choices is None
    assert f.help == ""


def test_command_with_bindings_roundtrip():
    cmd = Command(
        verb="update", object="application", variant=None, key="update:application",
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
