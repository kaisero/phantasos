"""IR built from the SDK's typed wrappers (`_WRAPPERS`/`_bindings`).

`cli_operations` walks the facade's `_WRAPPERS` (object -> wrapper class), reads each
wrapper's `_bindings` table, and emits one record PER BINDING keyed by the UNCHANGED
`api_resource.raw_method` so cli.yml continues to resolve. The two deltas vs. the old
raw-`*Api` introspection are dispatch-only: `Command.sdk_resource` becomes the OBJECT
attr (`client.<object>`) and `MethodBinding.sdk_method` becomes the clean wrapper verb.

Runs against the locally-built prisma-browser SDK at ``../prisma-browser-sdk``
(skips when absent).
"""

from __future__ import annotations

from pathlib import Path

from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.cliconfig import load_cli_config
from phantasos.generator.cli.ir import CliIR

CLI_YML = Path(__file__).parent.parent / "products" / "prisma-browser" / "cli.yml"


def _ir(real_sdk: Path) -> tuple[CliIR, list[str]]:
    inv = cli_operations("prisma_browser", real_sdk)
    return build_cli_ir(inv, load_cli_config(CLI_YML))


def test_ir_from_wrappers_no_unmapped(real_sdk: Path) -> None:
    ir, unmapped = _ir(real_sdk)
    keys = {c.key for c in ir.commands}
    # CRUD command for a plain object survives the rebase.
    assert {"create:device-group", "show:device-group", "delete:device-group"} <= keys
    # RA: one *Api fans out into three separate objects (rule/section/policy).
    assert "show:access-and-data-rule" in keys
    assert "show:access-and-data-section" in keys
    assert "show:access-and-data-policy" in keys
    # request/hide/variants/defaults keyed by api_resource.raw_method still resolve.
    assert unmapped == []
