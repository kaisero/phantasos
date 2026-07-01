"""T1: lazy command loading, proven on the federated `fedsdk` fixture.

The emitted federated CLI must import a command module ONLY when that command is
actually navigated to — a top-level or group-of-groups ``--help`` imports **zero**
``commands/*`` modules; a group-of-leaves ``--help`` imports only that level's leaf
module(s); a leaf ``--help``/dispatch imports exactly one. Import counts are checked
in a fresh SUBPROCESS because the in-process app + per-instance cache + ``sys.modules``
persist across ``CliRunner`` calls.

Behavioral parity (help text, did-you-mean, dispatch) is checked in-process. The
leaf command carries no ``--install-completion``/``--show-completion`` (it is built
via ``get_command_from_info``, not a throwaway ``typer.Typer()``).
"""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from phantasos.generator.cli.classify import build_cli_ir, build_ir, cli_operations
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.modelschema import build_model_registry
from phantasos.generator.cli.render_cli import render_cli
from phantasos.generator.opmodel._pathutil import on_sys_path

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"


def _fed_cfg() -> CliConfig:
    return CliConfig(
        subpackages={
            "alpha": CliConfig(),
            "beta": CliConfig(
                request={
                    "gadgets.compute_gadget": RequestMapping(
                        object="gadget", action="compute"
                    )
                }
            ),
        }
    )


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


def _render_fakesdk(out: Path) -> Path:
    # Request mappings give `fakesdk` its len-2 `request widget <action>` commands
    # (object group -> leaf), the single-spec analogue of the federated nesting.
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


# A fresh interpreter: build the app, invoke ONE argv, report the exit code, the
# emitted output, and which leaf command modules ended up imported. `pkg` selects
# the rendered distribution (federated `fedsdk_cli` by default, or `fakesdk_cli`).
_PROBE = r"""
import importlib, json, os, sys
os.environ.pop("FORCE_COLOR", None)
sys.path.insert(0, sys.argv[1])
pkg = sys.argv[2]
from typer.testing import CliRunner
app_mod = importlib.import_module(pkg + "._generated.app")
res = CliRunner().invoke(app_mod.build_generated_app(), sys.argv[3:])
pfx = pkg + "._generated.commands."
leaf = sorted(m for m in sys.modules if m.startswith(pfx))
out = {"exit": res.exit_code, "leaf": leaf, "output": res.output}
print("PROBE_JSON:" + json.dumps(out))
"""


def _probe(out: Path, *args: str, pkg: str = "fedsdk_cli") -> dict[str, Any]:
    proc = subprocess.run(  # noqa: S603 — trusted argv (sys.executable + fixed script)
        [sys.executable, "-c", _PROBE, str(out), pkg, *args],
        capture_output=True,
        text=True,
    )
    line = next(
        (ln for ln in proc.stdout.splitlines() if ln.startswith("PROBE_JSON:")), None
    )
    assert line is not None, f"probe produced no result:\n{proc.stdout}\n{proc.stderr}"
    result: dict[str, Any] = json.loads(line[len("PROBE_JSON:") :])
    return result


def _strip(s: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


# --- import counts (subprocess-isolated) ---


def test_top_help_imports_no_command_modules(tmp_path: Path) -> None:
    """Top `--help`: verbs render with ZERO `commands/*` modules imported."""
    out = _render_fedsdk(tmp_path)
    r = _probe(out, "--help")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == [], r["leaf"]
    text = _strip(r["output"])
    for verb in ("create", "update", "delete", "show", "request"):
        assert verb in text
    # config/which live in the CLI panel (proves the eager union still lists them)
    assert "config" in text and "which" in text


def test_group_of_groups_help_imports_nothing(tmp_path: Path) -> None:
    """`show --help` (group of SUB-PACKAGES) lists alpha/beta with ZERO imports —
    the child groups' help comes from the import-free _SUB_HELP dict."""
    out = _render_fedsdk(tmp_path)
    r = _probe(out, "show", "--help")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == [], r["leaf"]
    text = _strip(r["output"])
    assert "alpha" in text and "beta" in text
    assert "cli" in text  # the eager `show cli` child stays visible


def test_group_of_leaves_help_imports_that_level_only(tmp_path: Path) -> None:
    """`show alpha --help` (group of LEAVES) imports exactly that sub's leaf
    module(s) — here only `commands.widget` — and lists widget with its summary."""
    out = _render_fedsdk(tmp_path)
    r = _probe(out, "show", "alpha", "--help")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == ["fedsdk_cli._generated.commands.widget"], r["leaf"]
    assert "widget" in _strip(r["output"])


def test_leaf_help_imports_one_and_has_no_completion_flags(tmp_path: Path) -> None:
    """`show alpha widget --help`: exactly ONE import, real options + docstring
    summary, and NO --install/--show-completion (built via get_command_from_info,
    not a throwaway typer.Typer())."""
    out = _render_fedsdk(tmp_path)
    r = _probe(out, "show", "alpha", "widget", "--help")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == ["fedsdk_cli._generated.commands.widget"], r["leaf"]
    text = _strip(r["output"])
    assert "Get a widget by id." in text  # the show:widget docstring summary
    assert "--output" in text and "--dry-run" in text  # real leaf options
    assert "--install-completion" not in text
    assert "--show-completion" not in text


# --- behavioral parity (in-process) ---


def test_did_you_mean_fires_on_lazy_levels(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """did-you-mean fires for a mistyped verb (eager root) AND a mistyped
    sub-package/object (LAZY — the override sources candidates from list_commands,
    since a lazy group's self.commands is otherwise empty)."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app = importlib.import_module("fedsdk_cli._generated.app").build_generated_app()
        runner = CliRunner()

        r_verb = runner.invoke(app, ["shwo"])
        assert r_verb.exit_code == 2
        assert "Did you mean" in _strip(r_verb.output)
        assert "show" in _strip(r_verb.output)

        r_sub = runner.invoke(app, ["show", "alph"])  # lazy sub-package
        assert r_sub.exit_code == 2
        out_sub = _strip(r_sub.output)
        assert "Did you mean" in out_sub and "alpha" in out_sub

        r_obj = runner.invoke(app, ["show", "alpha", "widg"])  # lazy leaf
        assert r_obj.exit_code == 2
        out_obj = _strip(r_obj.output)
        assert "Did you mean" in out_obj and "widget" in out_obj


def test_excluded_leaf_neither_lists_nor_resolves(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """`exclude=` is honored in the lazy path: an excluded key's leaf disappears
    from its group's listing and fails to resolve."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"):
        app_mod = importlib.import_module("fedsdk_cli._generated.app")
        app = app_mod.build_generated_app(exclude={"show:widget"})
        runner = CliRunner()
        # alpha has only `widget`; excluding show:widget empties the listing (no
        # "Commands" panel) and the leaf no longer resolves.
        r_list = runner.invoke(app, ["show", "alpha", "--help"])
        assert "Commands" not in _strip(r_list.output)
        r_resolve = runner.invoke(app, ["show", "alpha", "widget"])
        assert r_resolve.exit_code == 2  # no such command


def _fake_fed_client(recorder: list[Any]) -> Any:
    class _ListResult:
        def __init__(self, data: list[Any]) -> None:
            self.data = data
            self.page_info = None

        def model_dump(self, *a: Any, **k: Any) -> dict[str, Any]:
            return {"data": self.data, "page_info": None}

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(*, all_pages: bool = False, **kw: Any) -> Any:
                recorder.append((name, kw))
                return _ListResult([{"id": "1"}]) if name == "list" else {"id": "x"}

            return _call

    class _Sub:
        def __init__(self) -> None:
            self.widget = _Rec()
            self.gadget = _Rec()

    class _Fed:
        def __init__(self) -> None:
            self.alpha = _Sub()
            self.beta = _Sub()

    return _Fed()


def test_lazy_leaf_dispatch_runs(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lazily-loaded leaf actually DISPATCHES (not just renders help): the
    `_facade_from_env` seam is monkeypatched, so `show alpha widget` navigates
    `client.alpha.widget.list(...)`."""
    from typer.testing import CliRunner

    out = _render_fedsdk(tmp_path)
    with render_and_import(out, "fedsdk_cli"), on_sys_path(FEDSDK):
        rt = importlib.import_module("fedsdk_cli._generated.runtime")
        calls: list[Any] = []
        monkeypatch.setattr(
            rt, "_facade_from_env", lambda **kw: _fake_fed_client(calls)
        )
        app = importlib.import_module("fedsdk_cli._generated.app").build_generated_app()
        r = CliRunner().invoke(app, ["show", "alpha", "widget", "--output", "json"])
        assert r.exit_code == 0, r.output
        assert any(name == "list" for name, _ in calls)


# --- single-spec (fakesdk) parity: the SAME _LazyGroup, 2-level verb->object ---


def test_ss_top_help_imports_no_command_modules(tmp_path: Path) -> None:
    """Single-spec top `--help`: verbs render with ZERO `commands/*` imports."""
    out = _render_fakesdk(tmp_path)
    r = _probe(out, "--help", pkg="fakesdk_cli")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == [], r["leaf"]
    text = _strip(r["output"])
    for verb in ("create", "update", "delete", "show", "request"):
        assert verb in text
    assert "config" in text  # the eager CLI-panel child stays listed


def test_ss_verb_group_of_leaves_imports_that_level(tmp_path: Path) -> None:
    """Single-spec `show --help` (a verb whose objects are LEAVES) imports exactly
    that verb's object modules — widget/gizmo/thing — and nothing deeper."""
    out = _render_fakesdk(tmp_path)
    r = _probe(out, "show", "--help", pkg="fakesdk_cli")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == [
        "fakesdk_cli._generated.commands.gizmo",
        "fakesdk_cli._generated.commands.thing",
        "fakesdk_cli._generated.commands.widget",
    ], r["leaf"]
    text = _strip(r["output"])
    assert "widget" in text and "gizmo" in text and "thing" in text
    assert "cli" in text  # the eager `show cli` child stays visible


def test_ss_leaf_help_imports_one_and_has_no_completion_flags(tmp_path: Path) -> None:
    """Single-spec leaf `show widget --help`: exactly ONE import, real options, and
    NO --install/--show-completion (built via get_command_from_info)."""
    out = _render_fakesdk(tmp_path)
    r = _probe(out, "show", "widget", "--help", pkg="fakesdk_cli")
    assert r["exit"] == 0, r["output"]
    assert r["leaf"] == ["fakesdk_cli._generated.commands.widget"], r["leaf"]
    text = _strip(r["output"])
    assert "--output" in text  # a real leaf option
    assert "--install-completion" not in text
    assert "--show-completion" not in text


def test_ss_did_you_mean_and_no_args_help(
    tmp_path: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """Single-spec did-you-mean fires at the eager root (mistyped verb) AND the lazy
    object level (mistyped object); `no_args_is_help` renders help at the root and at
    a verb group."""
    from typer.testing import CliRunner

    out = _render_fakesdk(tmp_path)
    with render_and_import(out, "fakesdk_cli"):
        app_mod = importlib.import_module("fakesdk_cli._generated.app")
        app = app_mod.build_generated_app()
        runner = CliRunner()

        r_verb = runner.invoke(app, ["shwo"])
        assert r_verb.exit_code == 2
        assert "Did you mean" in _strip(r_verb.output) and "show" in _strip(
            r_verb.output
        )

        r_obj = runner.invoke(app, ["show", "widdget"])  # lazy object
        assert r_obj.exit_code == 2
        out_obj = _strip(r_obj.output)
        assert "Did you mean" in out_obj and "widget" in out_obj

        # no_args_is_help: help rendered (not a crash) at the root and a verb group.
        r_root = runner.invoke(app, [])
        assert "show" in _strip(r_root.output)
        r_show = runner.invoke(app, ["show"])
        assert "widget" in _strip(r_show.output)
