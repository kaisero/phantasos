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

import pytest

from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.cliconfig import load_cli_config
from phantasos.generator.cli.ir import CliIR

REAL = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
CLI_YML = Path(__file__).parent.parent / "products" / "prisma-browser" / "cli.yml"

pytestmark = pytest.mark.skipif(
    not REAL.exists(), reason="prisma-browser SDK not built"
)


def _ir() -> tuple[CliIR, list[str]]:
    inv = cli_operations("prisma_browser", REAL)
    return build_cli_ir(inv, load_cli_config(CLI_YML))


def test_ir_from_wrappers_no_unmapped() -> None:
    ir, unmapped = _ir()
    keys = {c.key for c in ir.commands}
    # CRUD command for a plain object survives the rebase.
    assert {"create:device-group", "show:device-group", "delete:device-group"} <= keys
    # RA: one *Api fans out into three separate objects (rule/section/policy).
    assert "show:access-and-data-rule" in keys
    assert "show:access-and-data-section" in keys
    assert "show:access-and-data-policy" in keys
    # request/hide/variants/defaults keyed by api_resource.raw_method still resolve.
    assert unmapped == []
