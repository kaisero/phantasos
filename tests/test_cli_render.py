import json
from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import _py_name, render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_py_name_sanitizes_keywords_and_reserved():
    # Python keyword -> suffixed
    assert _py_name("from") == "from_"
    assert _py_name("class") == "class_"
    # reserved (collide with injected Typer options) -> suffixed
    assert _py_name("output") == "output_"
    assert _py_name("verbose") == "verbose_"
    # ordinary identifiers (incl. builtins, which are legal as params) -> unchanged
    assert _py_name("type") == "type"
    assert _py_name("name") == "name"
    assert _py_name("device_group_id") == "device_group_id"
    # non-identifier -> prefixed + cleaned
    assert _py_name("weird-name").startswith("p_")


def _ir():
    return build_cli_ir(introspect("fakesdk", FIXTURE), CliConfig())[0]


def test_render_cli_lays_down_project(tmp_path):
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


def test_emitted_spec_loads_ir_json_typed(tmp_path):
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


def test_render_cli_wipes_generated_but_preserves_handowned(tmp_path):
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    main = tmp_path / "fakesdk_cli" / "main.py"
    main.write_text("# user edits\n", encoding="utf-8")
    stale = tmp_path / "fakesdk_cli" / "_generated" / "stale.py"
    stale.write_text("# stale\n", encoding="utf-8")
    render_cli(_ir(), package="fakesdk_cli", out_dir=tmp_path)
    assert main.read_text() == "# user edits\n"   # hand-owned preserved
    assert not stale.exists()                       # _generated wiped


