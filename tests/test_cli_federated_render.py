"""C1: N-level Typer nesting — federated render emits verb -> sub-package -> object.

Renders the federated `fedsdk` CLI (subs alpha/beta) and asserts the emitted
`app.py` nests `show alpha widget` (len-2 path `[alpha, widget]`) and the len-3
`request beta gadget compute` (`[beta, gadget, compute]`); a Typer `CliRunner`
proves both resolve via `--help`. Also proves the single-spec (`fakesdk`) app.py
went lazy in lock-step — its 2-level `verb -> object -> leaf` commands resolve +
dispatch through the SAME `_LazyGroup` (no eager registration loop, no per-resource
imports, no federated-only `subpackage`/`_SUB_HELP` columns).
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType

from phantasos.generator.cli.classify import build_cli_ir, build_ir, cli_operations
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.ir import Command
from phantasos.generator.cli.modelschema import build_model_registry
from phantasos.generator.cli.render_cli import _command_view, render_cli

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"


def _fed_cfg() -> CliConfig:
    """Federated cli.yml mapping beta's non-CRUD `compute` (else the build fails
    loud); yields the len-3 `request beta gadget compute` path C1 must nest."""
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


def _render_fakesdk(out: Path) -> Path:
    # Request mappings give `fakesdk` its len-2 `request widget <action>` commands
    # (object group -> leaf) — the single-spec analogue of C1's nested path.
    cfg = CliConfig(
        request={
            "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
            "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
        }
    )
    inv = cli_operations("fakesdk", FAKESDK)
    ir = build_cli_ir(inv, cfg, models=build_model_registry("fakesdk", FAKESDK, inv))[0]
    render_cli(ir, package="fakesdk_cli", out_dir=out, env_prefix="FAKESDK")
    return out


def test_command_view_kebabs_subpackage_name() -> None:
    """The sub-package COMMAND name is kebab (`network_services`->`network-services`);
    the snake slug stays on the IR/dispatch (the `_REGISTRY` `subpackage` column)."""
    c = Command(
        verb="show",
        object="widget",
        key="show:widget",
        sdk_resource="widget",
        subpackage="network_services",
    )
    view = _command_view(c, set())
    assert view["typer_path"] == ["network-services", "widget"]
    assert view["subpackage"] == "network_services"  # snake retained for dispatch


def test_federated_app_registers_subpackage_level(tmp_path: Path) -> None:
    out = _render_fed(tmp_path)
    app = (out / "fedsdk_cli" / "_generated" / "app.py").read_text()
    # federated registry carries the snake slug column + a sub-package-prefixed
    # typer_path (assert the path literals; ruff may wrap the long rows).
    assert "# (key, verb, subpackage, typer_path, resource, func_name)" in app
    assert '["alpha", "widget"]' in app  # CRUD: [subpackage, object]
    # len-3: a request action nests [subpackage, object, leaf]
    assert '["beta", "gadget", "compute"]' in app
    # Lazy loading: the eager N-level registration loop + per-resource imports are
    # gone; a `_LazyGroup` serves verbs/subs/objects/leaves from a module-global tree.
    assert "class _LazyGroup" in app
    assert "_build_tree" in app
    assert "_cmd_" not in app  # no eager per-resource `import … as _cmd_<resource>`
    assert "range(1, len(path))" not in app  # the eager N-level loop is gone
    assert "obj, leaf = path" not in app


def test_federated_help_resolves_nested_commands(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    from typer.testing import CliRunner

    out = _render_fed(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()
        # len-2 CRUD: show -> alpha -> widget
        r1 = runner.invoke(app, ["show", "alpha", "widget", "--help"])
        assert r1.exit_code == 0, r1.output
        # len-3: request -> beta -> gadget -> compute
        r2 = runner.invoke(app, ["request", "beta", "gadget", "compute", "--help"])
        assert r2.exit_code == 0, r2.output
        # the sub-package level genuinely nests: `show alpha --help` lists `widget`
        r3 = runner.invoke(app, ["show", "alpha", "--help"])
        assert r3.exit_code == 0, r3.output
        assert "widget" in r3.output


def test_single_spec_app_is_lazy_2level(tmp_path: Path) -> None:
    """Single-spec (`fakesdk`) went lazy in lock-step with federated: the eager
    `object_apps` registration loop + per-resource imports are gone, replaced by the
    SAME `_LazyGroup` + `_Cmd`/`_TREE` — minus the federated-only `subpackage` column
    and `_SUB_HELP`/`_OBJ_HELP` help dicts."""
    out = _render_fakesdk(tmp_path)
    app = (out / "fakesdk_cli" / "_generated" / "app.py").read_text()
    # 5-tuple registry rows (no `subpackage`); the lazy machinery is shared.
    assert "# (key, verb, typer_path, resource, func_name)" in app
    assert '_Cmd("show:widget", "show", ["widget"], "widget", "show_widget")' in app
    assert "class _Cmd(NamedTuple):" in app
    assert "class _LazyGroup" in app and "_build_tree" in app
    # federated-only columns must NOT leak into the single-spec render.
    assert "subpackage" not in app
    assert "_SUB_HELP" not in app and "_OBJ_HELP" not in app
    # the eager registration loop + per-resource imports are gone.
    assert "object_apps" not in app
    assert "range(1, len(path))" not in app
    assert "obj, leaf = path" not in app
    assert "_cmd_" not in app


def test_single_spec_lazy_commands_resolve_and_list(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """The lazy 2-level single-spec app dispatches through `_LazyGroup`: a len-1
    `show widget` leaf and a len-2 `request widget suspend` (object group -> leaf)
    both resolve via `--help`, and the object group lists its leaves."""
    from typer.testing import CliRunner

    out = _render_fakesdk(tmp_path)
    with render_and_import(out, "fakesdk_cli"):
        app_mod = importlib.import_module("fakesdk_cli._generated.app")
        app = app_mod.build_generated_app()
        assert isinstance(app_mod.build_generated_app.__globals__["_LazyGroup"], type)
        runner = CliRunner()
        # len-1 path: verb -> object leaf.
        r1 = runner.invoke(app, ["show", "widget", "--help"])
        assert r1.exit_code == 0, r1.output
        # len-2 path: verb -> object group -> leaf.
        r2 = runner.invoke(app, ["request", "widget", "suspend", "--help"])
        assert r2.exit_code == 0, r2.output
        # the object group genuinely nests: `request widget --help` lists its leaves.
        r3 = runner.invoke(app, ["request", "widget", "--help"])
        assert r3.exit_code == 0, r3.output
        assert "suspend" in r3.output and "revoke" in r3.output
