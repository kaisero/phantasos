"""Pytest config for the phantasos framework engine tests.

Ensures the `phantasos` package (under src/) is importable even without an editable
install. SDK-specific tests live with each generated SDK, not here.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture
def emit_cli(tmp_path: Path) -> Callable[..., Path]:
    """Emit the fakesdk CLI into tmp_path for CLI-docs tests (tests/cli/).

    `auth=True` renders WITH an auth component so the IR carries credential_fields
    (exercises the credential-gated guides). Lives here rather than in
    tests/cli/conftest.py so there is a single `conftest` module name for mypy.
    """
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import (
        CliConfig,
        CliDocsConfig,
        RequestMapping,
        VariantMap,
    )
    from phantasos.generator.cli.render_cli import render_cli

    fixture = Path(__file__).parent / "fixtures" / "fakesdk"
    config = CliConfig(
        variants={
            "gizmos.create_gizmo": VariantMap(
                path_param="type",
                map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
            )
        },
        request={
            "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
            "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
        },
        defaults={"widgets.list_widgets": {"name": "gadget", "limit": 50}},
    )

    def _emit(*, docs: CliDocsConfig | None = None, auth: bool = False) -> Path:
        ir = build_cli_ir(cli_operations("fakesdk", fixture), config)[0]
        render_cli(
            ir,
            package="fakesdk_cli",
            out_dir=tmp_path,
            env_prefix="FAKESDK",
            distribution="fakesdk",
            auth=ScmOAuth(type="scm_oauth") if auth else None,
            docs=docs,
            docs_site_name="Fakesdk CLI",
        )
        return tmp_path

    return _emit
