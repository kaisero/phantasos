"""C1: N-level Typer nesting — federated render emits verb -> sub-package -> object.

Renders the federated `fedsdk` CLI (subs alpha/beta) and asserts the emitted
`app.py` nests `show alpha widget` (len-2 path `[alpha, widget]`) and the len-3
`request beta gadget compute` (`[beta, gadget, compute]`); a Typer `CliRunner`
proves both resolve via `--help`. Also pins the single-spec (`fakesdk`) app.py
build loop to its exact pre-federation 2-level form (a byte-identical slice), so
generalizing the loop to N levels did not perturb single-spec render output.
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
            "beta": CliConfig(
                request={
                    "gadgets.compute_gadget": RequestMapping(
                        object="gadget", action="compute"
                    )
                }
            )
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


# The exact pre-federation 2-level build loop (representative byte slice). Single-
# spec render must keep emitting this verbatim — the N-level loop is federated-only.
_SINGLE_SPEC_LOOP = """    object_apps: dict[tuple[str, str], typer.Typer] = {}
    for key, verb, path, resource, func_name in _REGISTRY:
        if key in exclude or verb not in verb_apps:
            continue
        fn = getattr(resources[resource], func_name)
        if len(path) == 1:
            verb_apps[verb].command(path[0])(fn)
        else:  # len 2: object sub-Typer under the verb, leaf inside it
            obj, leaf = path
            sub = object_apps.get((verb, obj))
            if sub is None:
                sub = typer.Typer(no_args_is_help=True)
                object_apps[(verb, obj)] = sub
                verb_apps[verb].add_typer(sub, name=obj)
            sub.command(leaf)(fn)
    return app"""


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
    # the generalized N-level loop replaced the 2-element unpack
    assert "range(1, len(path))" in app
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


def test_single_spec_app_loop_byte_identical(tmp_path: Path) -> None:
    inv = cli_operations("fakesdk", FAKESDK)
    ir = build_cli_ir(
        inv, CliConfig(), models=build_model_registry("fakesdk", FAKESDK, inv)
    )[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    app = (tmp_path / "fakesdk_cli" / "_generated" / "app.py").read_text()
    # single-spec keeps the exact pre-federation 5-tuple registry + 2-level loop
    assert "# (key, verb, typer_path, resource, func_name)" in app
    assert _SINGLE_SPEC_LOOP in app
    assert "subpackage" not in app  # no extra registry column leaks in
    assert "range(1, len(path))" not in app  # N-level loop stays federated-only
