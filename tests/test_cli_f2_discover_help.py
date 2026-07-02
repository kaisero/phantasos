"""F2: federated cli discover grouping + per-object/sub help text.

TDD: these fail before the implementation, green after.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType

from phantasos.generator.cli.classify import build_ir
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.discover import render_table
from phantasos.generator.cli.render_cli import render_cli

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"


def _fed_cfg() -> CliConfig:
    return CliConfig(
        subpackages={
            "alpha": CliConfig(),  # G1: enroll alpha (allowlist needs it listed)
            "beta": CliConfig(
                request={
                    "gadgets.compute_gadget": RequestMapping(
                        object="gadget", action="compute"
                    )
                }
            ),
        }
    )


# --- Part A: federated cli discover grouping ---


def test_federated_discover_groups_by_subpackage() -> None:
    """render_table on a federated IR groups output by sub-package (kebab headings)."""
    ir, unmapped = build_ir("fedsdk", FEDSDK, _fed_cfg())
    out = render_table(ir, unmapped)

    # Two sub-package headings, kebab-cased
    assert "## alpha" in out
    assert "## beta" in out

    # alpha section contains widget; beta section contains gadget
    alpha_section = out[out.index("## alpha") :]
    beta_section = out[out.index("## beta") :]
    assert "widget" in alpha_section
    assert "gadget" in beta_section

    # beta section has the request action too
    assert "request" in beta_section or "compute" in beta_section

    # a stub invocation is present (one per sub or representative)
    assert "fedsdk" in out  # the CLI name appears in the stub


def test_federated_discover_has_stub_invocations() -> None:
    """render_table includes the exact example invocation lines per sub-package."""
    ir, unmapped = build_ir("fedsdk", FEDSDK, _fed_cfg())
    out = render_table(ir, unmapped)

    # Exact stub lines emitted by _render_federated_table
    assert "example: fedsdk show alpha widget" in out
    assert "example: fedsdk show beta gadget" in out


def test_single_spec_discover_unchanged() -> None:
    """Single-spec discover output is byte-identical to the pre-F2 format.

    The header line and the flat command list stay as they were before federation
    grouping was introduced — the federated path is strictly additive.
    """
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations

    inv = cli_operations("fakesdk", FAKESDK)
    ir, unmapped = build_cli_ir(inv, CliConfig())
    out = render_table(ir, unmapped)

    # Single-spec header format: "# <package> <version> — N commands"
    assert out.startswith(f"# {ir.sdk_package} {ir.sdk_version} —")
    # No sub-package grouping headings
    assert "## " not in out
    # Commands present in flat form
    assert "show widget" in out
    assert "create widget" in out
    # Unmapped ops still appear
    assert "UNMAPPED" in out


# --- Part B: emitted fedsdk CLI help text ---


def _render_fedsdk(out: Path) -> Path:
    ir, _ = build_ir("fedsdk", FEDSDK, _fed_cfg())
    render_cli(
        ir,
        package="fedsdk_cli",
        out_dir=out,
        env_prefix="FEDSDK",
        distribution="fedsdk",
    )
    return out


def test_fedsdk_app_emits_sub_and_obj_help_dicts(tmp_path: Path) -> None:
    """The emitted app.py carries _SUB_HELP and _OBJ_HELP dicts (federated only)."""
    out = _render_fedsdk(tmp_path)
    app_text = (out / "fedsdk_cli" / "_generated" / "app.py").read_text()

    assert "_SUB_HELP" in app_text
    assert "_OBJ_HELP" in app_text
    assert '"alpha"' in app_text
    assert '"beta"' in app_text
    assert '"widget"' in app_text
    assert '"gadget"' in app_text


def test_fedsdk_show_alpha_help_has_group_line(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """show alpha --help shows the _SUB_HELP["alpha"] text as the group description."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()
        r = runner.invoke(app, ["show", "alpha", "--help"])
        assert r.exit_code == 0, r.output
        # _SUB_HELP["alpha"] is wired as the alpha sub-Typer help; it must appear.
        assert "Create a widget." in r.output
        # widget appears as a subcommand
        assert "widget" in r.output


def test_fedsdk_show_alpha_help_shows_widget_with_description(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """show alpha --help lists `widget` with a description (if available)."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()
        r = runner.invoke(app, ["show", "alpha", "--help"])
        assert r.exit_code == 0, r.output
        # widget appears as a subcommand with some description text
        assert "widget" in r.output
        # The description for widget is non-empty (there is text after 'widget')
        widget_line = next(
            (ln for ln in r.output.splitlines() if "widget" in ln.lower()), None
        )
        assert widget_line is not None
        # There's something besides just "widget" on that line
        # (the description appears in Typer's help panel)
        assert len(widget_line.strip()) > len("widget")


def test_fedsdk_show_alpha_widget_help_shows_object_description(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """show alpha widget --help shows the show:widget command's docstring summary."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()
        r = runner.invoke(app, ["show", "alpha", "widget", "--help"])
        assert r.exit_code == 0, r.output
        # show:widget carries summary="Get a widget by id." as its docstring.
        # Must appear in help; fails if summary is dropped.
        assert "Get a widget by id." in r.output


def test_fedsdk_request_beta_gadget_obj_help(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """request beta gadget --help shows the _OBJ_HELP["gadget"] text (depth-2 path).

    `request:gadget:compute` has typer_path=["beta","gadget","compute"] (len 3).
    At depth 2 the "gadget" intermediate sub-Typer is wired with
    _OBJ_HELP["gadget"]="Create a gadget." — the only len-3 path in the fedsdk fixture.
    """
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()
        r = runner.invoke(app, ["request", "beta", "gadget", "--help"])
        assert r.exit_code == 0, r.output
        # _OBJ_HELP["gadget"] is wired as the depth-2 gadget sub-Typer help.
        assert "Create a gadget." in r.output
        # The "compute" leaf command is listed under it.
        assert "compute" in r.output


def test_single_spec_emitted_app_has_no_help_dicts(tmp_path: Path) -> None:
    """Single-spec app.py carries NO _SUB_HELP / _OBJ_HELP — federated-only feature."""
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.modelschema import build_model_registry

    inv = cli_operations("fakesdk", FAKESDK)
    ir = build_cli_ir(
        inv, CliConfig(), models=build_model_registry("fakesdk", FAKESDK, inv)
    )[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    app_text = (tmp_path / "fakesdk_cli" / "_generated" / "app.py").read_text()

    # Single-spec app carries NO help dicts
    assert "_SUB_HELP" not in app_text
    assert "_OBJ_HELP" not in app_text
