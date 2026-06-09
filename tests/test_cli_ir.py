from phantasos.generator.cli.ir import CliIR, Command, Flag


def test_flag_defaults():
    f = Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)
    assert f.default is None
    assert f.choices is None
    assert f.help == ""


def test_command_and_ir_roundtrip():
    cmd = Command(
        verb="set", object="widget", sdk_resource="widgets", sdk_method="create_widget",
        body_flags=[Flag(name="--name", param="name", py_type="str", kind="scalar", required=True)],
    )
    ir = CliIR(sdk_package="fakesdk", sdk_version="9.9.9", commands=[cmd])
    assert ir.commands[0].verb == "set"
    assert ir.commands[0].variant is None
    # round-trips through JSON (used for _generated/ir.json in Phase 2)
    assert CliIR.model_validate_json(ir.model_dump_json()) == ir
