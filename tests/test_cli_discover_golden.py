import json
from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.cliconfig import load_cli_config
from phantasos.generator.cli.ir import CliIR

GOLD = Path(__file__).parent / "golden" / "prisma-browser.tree.json"


def project_tree(ir: CliIR) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for c in sorted(ir.commands, key=lambda c: c.key):
        flag_dicts: list[dict[str, str | bool]] = [
            {"name": f.name, "kind": f.kind, "required": f.required}
            for f in (c.path_params + c.body_flags + c.query_flags)
        ]
        out.append(
            {
                "key": c.key,
                "verb": c.verb,
                "object": c.object,
                "variant": c.variant,
                "action": c.action,
                "flags": sorted(flag_dicts, key=lambda d: str(d["name"])),
                "columns": [col.header for col in c.columns],
            }
        )
    return out


def _build_ir(real_sdk: Path) -> CliIR:
    inv = cli_operations("prisma_browser", real_sdk)  # walks _WRAPPERS/_bindings (T4.1)
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    return ir


def test_command_tree_matches_golden(real_sdk: Path) -> None:
    assert project_tree(_build_ir(real_sdk)) == json.loads(GOLD.read_text())
