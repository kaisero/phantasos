import json
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.ir import CliIR, Flag
from phantasos.generator.cli.render_cli import _py_name, _render_type, render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_bool_scalar_renders_as_value_taking_option() -> None:
    # Typer treats a `bool` annotation as an on/off flag that takes NO value, so a
    # settable bool field (e.g. --route-to-prisma) must render as a value-taking
    # option and be coerced to bool at runtime. Required -> bare `str`; optional ->
    # the `str | None` union. (See test_bool_body_flag_* for the runtime coercion.)
    req = Flag(
        name="--route-to-prisma",
        param="route_to_prisma",
        py_type="bool",
        kind="scalar",
        required=True,
    )
    opt = Flag(
        name="--enabled", param="enabled", py_type="bool", kind="scalar", required=False
    )
    assert _render_type(req) == "str"
    assert _render_type(opt) == "str | None"


def test_int_scalar_still_renders_native_type() -> None:
    # Regression guard: non-bool scalars keep their REAL Python type so Typer
    # validates them itself (only bool needs the str-then-coerce treatment).
    f = Flag(
        name="--priority", param="priority", py_type="int", kind="scalar", required=True
    )
    assert _render_type(f) == "int"


def test_py_name_sanitizes_keywords_and_reserved() -> None:
    # Python keyword -> suffixed
    assert _py_name("from") == "from_"
    assert _py_name("class") == "class_"
    # reserved (collide with injected Typer options) -> suffixed
    assert _py_name("output") == "output_"
    assert _py_name("verbose") == "verbose_"
    assert _py_name("pager") == "pager_"
    # ordinary identifiers (incl. builtins, which are legal as params) -> unchanged
    assert _py_name("type") == "type"
    assert _py_name("name") == "name"
    assert _py_name("device_group_id") == "device_group_id"
    # non-identifier -> prefixed + cleaned
    assert _py_name("weird-name").startswith("p_")


def _ir() -> CliIR:
    return build_cli_ir(introspect("fakesdk", FIXTURE), CliConfig())[0]


def test_render_cli_lays_down_project(tmp_path: Path) -> None:
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    gen = tmp_path / "fakesdk_cli" / "_generated"
    assert (gen / "__init__.py").exists()
    assert (gen / "ir.json").exists()
    assert (gen / "spec.py").exists()
    assert (tmp_path / "fakesdk_cli" / "main.py").exists()
    assert (tmp_path / "fakesdk_cli" / "hooks.py").exists()
    assert (tmp_path / "fakesdk_cli" / "custom" / "__init__.py").exists()
    data = json.loads((gen / "ir.json").read_text())
    assert {c["key"] for c in data["commands"]} == {c.key for c in _ir().commands}


def test_emitted_spec_loads_ir_json_typed(tmp_path: Path) -> None:
    # H1: the emitted spec.py + ir.json round-trip through the TYPED CliIR
    import importlib
    import sys

    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    try:
        for n in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[n]
        spec = importlib.import_module("fakesdk_cli._generated.spec")
        ir_json = (tmp_path / "fakesdk_cli" / "_generated" / "ir.json").read_text()
        loaded = spec.CliIR.model_validate_json(ir_json)
        assert {c.key for c in loaded.commands} == {c.key for c in _ir().commands}
        # a binding's typed fields are accessible (no raw-dict access needed at runtime)
        setw = next(c for c in loaded.commands if c.key == "create:widget")
        assert any(b.body_model == "WidgetInput" for b in setw.bindings)
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[n]


def test_render_cli_wipes_generated_but_preserves_handowned(tmp_path: Path) -> None:
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    main = tmp_path / "fakesdk_cli" / "main.py"
    main.write_text("# user edits\n", encoding="utf-8")
    stale = tmp_path / "fakesdk_cli" / "_generated" / "stale.py"
    stale.write_text("# stale\n", encoding="utf-8")
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    assert main.read_text() == "# user edits\n"  # hand-owned preserved
    assert not stale.exists()  # _generated wiped


def test_render_rejects_reserved_cli_object(tmp_path: Path) -> None:
    from phantasos.generator.cli.ir import CliIR, Command, MethodBinding

    ir = CliIR(
        sdk_package="x",
        sdk_version="0.0.0",
        commands=[
            Command(
                verb="show",
                object="cli",
                key="show:cli",
                sdk_resource="clis",
                bindings=[MethodBinding(sdk_method="list_clis", sub_verb="list")],
            )
        ],
    )
    with pytest.raises(ValueError, match="reserved"):
        render_cli(ir, package="x_cli", out_dir=tmp_path)


def test_render_cli_emits_diagnostics_module(tmp_path: Path) -> None:
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    assert (tmp_path / "fakesdk_cli" / "_generated" / "diagnostics.py").exists()


def _diag(base: Path) -> str:
    return (base / "fakesdk_cli" / "_generated" / "diagnostics.py").read_text()


def test_error_envelope_threaded_from_component(tmp_path: Path) -> None:
    from phantasos.config import ListError, NestedError

    # list_error -> errors_field descriptor flows into diagnostics + ir.json
    render_cli(
        _ir(),
        package="fakesdk_cli",
        out_dir=tmp_path / "list",
        errors=ListError(type="list_error"),
    )
    diag = _diag(tmp_path / "list")
    assert '"errors_field": "_errors"' in diag and '"error_field": None' in diag
    ir_json = json.loads(
        (tmp_path / "list" / "fakesdk_cli" / "_generated" / "ir.json").read_text()
    )
    assert ir_json["error_envelope"]["errors_field"] == "_errors"

    # nested -> wrapper + error_field; the `errorResponse` wrapper is config and
    # appears ONLY in this product's CLI (not leaked into others)
    render_cli(
        _ir(),
        package="fakesdk_cli",
        out_dir=tmp_path / "nested",
        errors=NestedError(type="nested"),
    )
    diag2 = _diag(tmp_path / "nested")
    assert '"error_field": "error"' in diag2 and "errorResponse" in diag2
    assert '"errors_field": None' in diag2


def test_no_error_component_emits_generic_envelope(tmp_path: Path) -> None:
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)  # no errors=
    diag = _diag(tmp_path)
    # default envelope: zero product shapes baked into the generic template
    assert "errorResponse" not in diag and '"_errors"' not in diag
    assert '"error_field": None' in diag and '"errors_field": None' in diag


def test_flag_view_injects_json_annotation_and_skeleton() -> None:
    from phantasos.generator.cli.ir import Flag, ModelField, ModelSchema
    from phantasos.generator.cli.render_cli import _flag_view

    models = {
        "WidgetProfile": ModelSchema(
            fields=[
                ModelField(
                    name="contact",
                    alias="contact",
                    py_type="str",
                    kind="json",
                    required=False,
                    model_ref="Contact",
                ),
            ]
        ),
        "Contact": ModelSchema(
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
        required=False,
        help="Widget profile.",
        model_ref="WidgetProfile",
    )
    view = _flag_view(f, models=models)
    help_literal = view["help_literal"]
    assert isinstance(help_literal, str)
    assert "[json: WidgetProfile]" in help_literal
    assert '{\\"contact\\":{\\"name\\":\\"string\\"}}' in help_literal
