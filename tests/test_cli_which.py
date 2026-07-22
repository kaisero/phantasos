"""F1: `which <object>` federated discoverability command.

Verifies:
- `which widget` resolves to alpha + its verbs (create/show/update/delete)
- `which gadget` resolves to beta + its verbs incl. `request`
- `which <typo>` exits non-zero with a Did-you-mean message
- `which <totally-unknown>` exits non-zero without crashing
- Single-spec (`fakesdk`) does NOT emit `which_object` (federated-only gate)
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

from phantasos.generator.cli.classify import build_cli_ir, build_ir, cli_operations
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.modelschema import build_model_registry
from phantasos.generator.cli.render_cli import render_cli

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"


def _fed_cfg() -> CliConfig:
    return CliConfig(
        subpackages={
            "alpha": CliConfig(),  # G1: enroll alpha (allowlist needs it listed)
            "beta": CliConfig(request={"gadgets.compute_gadget": RequestMapping(object="gadget", action="compute")}),
        }
    )


def _render_fed(out: Path) -> Path:
    ir, _ = build_ir("fedsdk", FEDSDK, _fed_cfg())
    render_cli(
        ir,
        package="fedsdk_cli",
        out_dir=out,
        env_prefix="FEDSDK",
        distribution="fedsdk",
    )
    return out


@pytest.fixture
def fed_app(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> Iterator[tuple[CliRunner, Any]]:
    """Render the federated fedsdk_cli and yield a (runner, app) pair."""
    out = _render_fed(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        yield CliRunner(), app_mod.build_generated_app()


def test_which_widget_resolves_to_alpha(fed_app: tuple[CliRunner, Any]) -> None:
    runner, app = fed_app
    result = runner.invoke(app, ["which", "widget"])
    assert result.exit_code == 0, result.output
    assert "widget" in result.output
    assert "alpha" in result.output
    # at least one verb present
    assert "show" in result.output or "create" in result.output


def test_which_gadget_resolves_to_beta_with_request(
    fed_app: tuple[CliRunner, Any],
) -> None:
    runner, app = fed_app
    result = runner.invoke(app, ["which", "gadget"])
    assert result.exit_code == 0, result.output
    assert "gadget" in result.output
    assert "beta" in result.output
    assert "request" in result.output


def test_which_typo_exits_nonzero_with_did_you_mean(
    fed_app: tuple[CliRunner, Any],
) -> None:
    runner, app = fed_app
    result = runner.invoke(app, ["which", "wodget"])
    assert result.exit_code != 0
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "Did you mean" in combined


def test_which_totally_unknown_exits_nonzero_no_crash(
    fed_app: tuple[CliRunner, Any],
) -> None:
    runner, app = fed_app
    result = runner.invoke(app, ["which", "xyzzy12345abcdef"])
    assert result.exit_code != 0
    combined = result.output + (getattr(result, "stderr", "") or "")
    assert "unknown object" in combined


def test_single_spec_has_no_which_object(tmp_path: Path) -> None:
    """Federated-only gate: single-spec (`fakesdk`) must NOT emit `which_object`."""
    inv = cli_operations("fakesdk", FAKESDK)
    ir = build_cli_ir(inv, CliConfig(), models=build_model_registry("fakesdk", FAKESDK, inv))[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    cli_cmds = (tmp_path / "fakesdk_cli" / "_generated" / "cli_commands.py").read_text()
    app_py = (tmp_path / "fakesdk_cli" / "_generated" / "app.py").read_text()
    assert "which_object" not in cli_cmds
    assert "which_object" not in app_py
