from phantasos.generator.cli.examples import example_value, render_invocation
from phantasos.generator.cli.ir import (
    Command,
    Flag,
    FlagKind,
    ModelField,
    ModelSchema,
)


def _flag(
    name: str,
    *,
    py_type: str = "str",
    kind: FlagKind = "scalar",
    required: bool = True,
    choices: list[str] | None = None,
) -> Flag:
    return Flag(
        name=name,
        param=name.lstrip("-").replace("-", "_"),
        py_type=py_type,
        kind=kind,
        required=required,
        choices=choices,
    )


def test_example_value_by_type() -> None:
    assert example_value(_flag("--name", py_type="str")) == '"example"'
    assert example_value(_flag("--count", py_type="int")) == "0"
    assert example_value(_flag("--ratio", py_type="float")) == "0.0"
    assert example_value(_flag("--on", py_type="bool")) == "true"
    assert example_value(_flag("--color", kind="enum", choices=["red", "blue"])) == "red"
    assert example_value(_flag("--body", kind="json")) == "'{}'"
    assert example_value(_flag("--file", kind="file")) == "./file"
    assert example_value(_flag("--id", kind="id")) == '"example"'


def test_example_value_renders_minimal_skeleton_for_json() -> None:
    models = {
        "P": ModelSchema(
            fields=[
                ModelField(
                    name="contact",
                    alias="contact",
                    py_type="str",
                    kind="json",
                    required=False,
                    model_ref="C",
                ),
            ]
        ),
        "C": ModelSchema(
            fields=[
                ModelField(
                    name="name",
                    alias="name",
                    py_type="str",
                    kind="scalar",
                    required=True,
                ),
            ]
        ),
    }
    f = Flag(
        name="--profile",
        param="profile",
        py_type="str",
        kind="json",
        required=True,
        model_ref="P",
    )
    assert example_value(f, models) == '\'{"contact":{"name":"string"}}\''


def test_example_value_anonymous_json_falls_back() -> None:
    f = Flag(name="--spec", param="spec", py_type="str", kind="json", required=True)
    assert example_value(f, {}) == "'{}'"


def test_render_invocation_required_only() -> None:
    cmd = Command(
        verb="create",
        object="widget",
        key="create:widget",
        sdk_resource="widgets",
        path_params=[_flag("--id")],
        body_flags=[_flag("--name"), _flag("--note", required=False)],
        query_flags=[_flag("--limit", py_type="int", required=False)],
    )
    assert render_invocation(cmd, distribution="acmecli") == ('acmecli create widget --id "example" --name "example"')


def test_render_invocation_leaf_and_override() -> None:
    variant = Command(
        verb="create",
        object="gizmo",
        variant="simple",
        key="create:gizmo:simple",
        sdk_resource="gizmos",
        body_flags=[_flag("--name")],
    )
    assert render_invocation(variant, distribution="acmecli") == ('acmecli create gizmo simple --name "example"')
    # override is returned verbatim after stripping surrounding whitespace
    assert render_invocation(variant, distribution="acmecli", override="  acmecli foo  ") == "acmecli foo"
    # the leaf segment also covers a request `action` (not just a oneOf `variant`)
    action = Command(
        verb="request",
        object="widget",
        action="suspend",
        key="request:widget:suspend",
        sdk_resource="widgets",
        path_params=[_flag("--id")],
    )
    assert render_invocation(action, distribution="acmecli") == ('acmecli request widget suspend --id "example"')
