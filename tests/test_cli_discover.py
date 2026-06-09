from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.discover import render_stub, render_table
from phantasos.generator.cli.introspect import introspect

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def _ir_and_unmapped():
    inv = introspect("fakesdk", FIXTURE)
    return build_cli_ir(inv, CliConfig())


def test_render_table_lists_commands_and_unmapped():
    ir, unmapped = _ir_and_unmapped()
    table = render_table(ir, unmapped)
    assert "set widget" in table
    assert "show widget" in table
    assert "UNMAPPED" in table
    assert "widgets.update_widget_positions" in table


def test_render_stub_is_valid_yaml_with_todos():
    import io

    from ruamel.yaml import YAML

    ir, unmapped = _ir_and_unmapped()
    stub = render_stub(ir, unmapped)
    data = YAML(typ="safe").load(io.StringIO(stub))
    # unmapped ops appear under a commented TODO section as request/hide candidates
    assert "request" in data or "hide" in data
    assert "update_widget_positions" in stub  # surfaced as a TODO


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_real_sdk_classifies_without_error():
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(
            f"prisma-browser-sdk runtime deps not installed in this venv: {exc}"
        )
    ir, unmapped = build_cli_ir(inv, CliConfig())
    verbs = {c.verb for c in ir.commands}
    assert {"set", "del", "show"} <= verbs
    # non-CRUD ops land in unmapped (force_reauth/positions/publish/etc.)
    assert any("positions" in u or "force" in u or "publish" in u for u in unmapped)
