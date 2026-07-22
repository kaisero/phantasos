from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.discover import render_stub, render_table
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.ir import CliIR

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def _ir_and_unmapped() -> tuple[CliIR, list[str]]:
    inv = introspect("fakesdk", FIXTURE)
    return build_cli_ir(inv, CliConfig())


def test_render_table_lists_commands_and_unmapped() -> None:
    ir, unmapped = _ir_and_unmapped()
    table = render_table(ir, unmapped)
    assert "create widget" in table
    assert "show widget" in table
    # bindings are shown for a merged command (get + list under one show)
    assert "get_widget_by_id" in table and "list_widgets" in table
    assert "UNMAPPED" in table
    assert "widgets.update_widget_positions" in table


def test_command_keys_are_unique() -> None:
    ir, _ = _ir_and_unmapped()
    keys = [c.key for c in ir.commands]
    assert len(keys) == len(set(keys))  # aggregation produced no duplicate commands


def test_render_stub_is_valid_yaml_with_todos() -> None:
    import io

    from ruamel.yaml import YAML

    ir, unmapped = _ir_and_unmapped()
    stub = render_stub(ir, unmapped)
    data = YAML(typ="safe").load(io.StringIO(stub))
    # unmapped ops appear under a commented TODO section as request/hide candidates
    assert "request" in data or "hide" in data
    assert "update_widget_positions" in stub  # surfaced as a TODO


def test_stub_prefills_columns_from_defaults() -> None:
    from phantasos.generator.cli.discover import render_stub
    from phantasos.generator.cli.ir import CliIR, ColumnSpec, Command

    ir = CliIR(
        sdk_package="x",
        sdk_version="1",
        commands=[
            Command(
                verb="show",
                object="widget",
                key="show:widget",
                sdk_resource="widgets",
                columns=[
                    ColumnSpec(header="id", path="id"),
                    ColumnSpec(header="name", path="name"),
                ],
            ),
            Command(
                verb="create",
                object="widget",
                key="create:widget",
                sdk_resource="widgets",
                columns=[
                    ColumnSpec(header="id", path="id"),
                    ColumnSpec(header="name", path="name"),
                ],
            ),
            Command(verb="show", object="gizmo", key="show:gizmo", sdk_resource="gizmos"),  # no columns -> omitted
        ],
    )
    stub = render_stub(ir, [])
    assert "columns:" in stub
    assert "widget: [id, name]" in stub
    assert stub.count("widget:") == 1  # deduped across verbs
    assert "gizmo:" not in stub


def test_real_sdk_classifies_without_error(real_sdk: Path) -> None:
    try:
        inv = introspect("prisma_browser", real_sdk)
    except ImportError as exc:
        pytest.skip(f"prisma-browser-sdk runtime deps not installed in this venv: {exc}")
    ir, unmapped = build_cli_ir(inv, CliConfig())
    # no duplicate commands
    assert len({c.key for c in ir.commands}) == len(ir.commands)
    verbs = {c.verb for c in ir.commands}
    assert {"create", "update", "delete", "show"} <= verbs
    # non-CRUD ops land in unmapped (force_reauth/positions/publish/etc.)
    assert any("positions" in u or "force" in u or "publish" in u for u in unmapped)
