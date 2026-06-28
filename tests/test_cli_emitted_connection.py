"""D2: the emitted CLI surfaces a product's connection-header fields (region/tenant).

Connection fields (`ir.connection_fields`, contributed by `default_headers`) ride
the SAME seams as credentials: prompted/stored per named environment, exported to
their `env` var BEFORE the SDK Client is built (the SDK reads `FEDSDK_REGION` etc.
from the environment), and overridable by a per-field global flag layered
`--flag > env var > active-environment value`.

The federated `fedsdk` fixture is the vehicle: rendered WITH a `Region`/`FEDSDK_REGION`
header so `ir.connection_fields` is populated. Single-spec `fakesdk` (no headers)
must emit and behave identically — no `--region` flag, no connection export.
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
import yaml

from phantasos.generator.cli.classify import build_cli_ir, build_ir, cli_operations
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping
from phantasos.generator.cli.modelschema import build_model_registry
from phantasos.generator.cli.render_cli import render_cli
from phantasos.generator.opmodel._pathutil import on_sys_path
from phantasos.productconfig import HeaderSpec

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _fed_cfg() -> CliConfig:
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


_REGION_HEADERS = {"Region": HeaderSpec(env="FEDSDK_REGION", required_for=["beta"])}


@contextmanager
def _fed_cli(tmp_path: Path) -> Iterator[None]:
    """Render the fedsdk CLI WITH the Region connection header and import it."""
    ir, _ = build_ir("fedsdk", FEDSDK, _fed_cfg())
    render_cli(
        ir,
        package="fedsdk_cli",
        out_dir=tmp_path,
        env_prefix="FEDSDK",
        distribution="fedsdk",
        default_headers=_REGION_HEADERS,
    )
    entry = str(tmp_path)
    added = entry not in sys.path
    if added:
        sys.path.insert(0, entry)
    purge = [m for m in sys.modules if m == "fedsdk_cli" or m.startswith("fedsdk_cli.")]
    for m in purge:
        del sys.modules[m]
    try:
        with on_sys_path(FEDSDK):
            yield
    finally:
        for m in [
            n for n in sys.modules if n == "fedsdk_cli" or n.startswith("fedsdk_cli.")
        ]:
            del sys.modules[m]
        if added and entry in sys.path:
            sys.path.remove(entry)


def _read_envs(home: Path) -> dict[str, Any]:
    text = (home / ".fedsdk" / "environments.yml").read_text(encoding="utf-8")
    data: dict[str, Any] = yaml.safe_load(text)
    return data


def test_create_stores_region_and_show_displays_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    with _fed_cli(tmp_path / "out"):
        main = importlib.import_module("fedsdk_cli.main")

        # the per-field connection flag is derived from the header (Region -> region)
        create_help = _strip_ansi(
            CliRunner().invoke(main.app, ["environment", "create", "--help"]).output
        )
        assert "--region" in create_help

        res = CliRunner().invoke(
            main.app, ["environment", "create", "prod", "--region", "us"]
        )
        assert res.exit_code == 0, res.output
        data = _read_envs(home)
        assert data["environments"]["prod"]["region"] == "us"

        # non-secret: the value is shown by `environment show`
        show = _strip_ansi(CliRunner().invoke(main.app, ["environment", "show"]).output)
        assert "us" in show


def test_active_environment_region_exported_before_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".fedsdk").mkdir(parents=True)
    (home / ".fedsdk" / "environments.yml").write_text(
        "default_environment: prod\nenvironments:\n  prod: {region: eu}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FEDSDK_REGION", raising=False)
    monkeypatch.delenv("FEDSDK_ENVIRONMENT", raising=False)
    with _fed_cli(tmp_path / "out"):
        rt = importlib.import_module("fedsdk_cli._generated.runtime")
        seen: dict[str, Any] = {}

        def _fake(**kw: Any) -> Any:
            seen["region"] = os.environ.get("FEDSDK_REGION")  # set BEFORE the client
            return object()

        monkeypatch.setattr(rt, "_facade_from_env", _fake)
        rt._client()
        assert seen["region"] == "eu"


def test_flag_overrides_active_environment_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".fedsdk").mkdir(parents=True)
    (home / ".fedsdk" / "environments.yml").write_text(
        "default_environment: prod\nenvironments:\n  prod: {region: eu}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FEDSDK_REGION", raising=False)
    monkeypatch.delenv("FEDSDK_ENVIRONMENT", raising=False)
    with _fed_cli(tmp_path / "out"):
        rt = importlib.import_module("fedsdk_cli._generated.runtime")
        seen: dict[str, Any] = {}

        def _fake(**kw: Any) -> Any:
            seen["region"] = os.environ.get("FEDSDK_REGION")
            return object()

        monkeypatch.setattr(rt, "_facade_from_env", _fake)
        rt.set_connection_overrides({"FEDSDK_REGION": "ap"})  # the --region flag
        try:
            rt._client()
            assert seen["region"] == "ap"  # flag beats the active-env value (eu)
        finally:
            rt.set_connection_overrides({})


def test_env_var_beats_active_environment_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    (home / ".fedsdk").mkdir(parents=True)
    (home / ".fedsdk" / "environments.yml").write_text(
        "default_environment: prod\nenvironments:\n  prod: {region: eu}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FEDSDK_REGION", "shell")  # exported -> beats active-env
    monkeypatch.delenv("FEDSDK_ENVIRONMENT", raising=False)
    with _fed_cli(tmp_path / "out"):
        rt = importlib.import_module("fedsdk_cli._generated.runtime")
        seen: dict[str, Any] = {}

        def _fake(**kw: Any) -> Any:
            seen["region"] = os.environ.get("FEDSDK_REGION")
            return object()

        monkeypatch.setattr(rt, "_facade_from_env", _fake)
        rt._client()
        assert seen["region"] == "shell"


def test_region_flag_threads_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    (home / ".fedsdk").mkdir(parents=True)
    (home / ".fedsdk" / "environments.yml").write_text(
        "default_environment: prod\nenvironments:\n  prod: {region: eu}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FEDSDK_REGION", raising=False)
    monkeypatch.delenv("FEDSDK_ENVIRONMENT", raising=False)
    with _fed_cli(tmp_path / "out"):
        rt = importlib.import_module("fedsdk_cli._generated.runtime")
        main = importlib.import_module("fedsdk_cli.main")

        seen: dict[str, Any] = {}

        class _Rec:
            def __getattr__(self, name: str) -> Any:
                def _call(*, all_pages: bool = False, **kw: Any) -> Any:
                    return []

                return _call

        class _Sub:
            def __init__(self) -> None:
                self.widget = _Rec()

        class _Fed:
            def __init__(self) -> None:
                self.alpha = _Sub()

        def _fake(**kw: Any) -> Any:
            seen["region"] = os.environ.get("FEDSDK_REGION")
            return _Fed()

        monkeypatch.setattr(rt, "_facade_from_env", _fake)
        res = CliRunner().invoke(
            main.app,
            ["show", "alpha", "widget", "--region", "ap", "--output", "json"],
        )
        assert res.exit_code == 0, res.output
        assert seen["region"] == "ap"  # the global --region flag won


def _render_single_spec(out: Path) -> Path:
    inv = cli_operations("fakesdk", FAKESDK)
    ir = build_cli_ir(
        inv, CliConfig(), models=build_model_registry("fakesdk", FAKESDK, inv)
    )[0]
    render_cli(ir, package="fakesdk_cli", out_dir=out, env_prefix="FAKESDK")
    return out


def test_single_spec_has_no_connection_flag_or_export(tmp_path: Path) -> None:
    out = _render_single_spec(tmp_path)
    gen = out / "fakesdk_cli" / "_generated"
    for mod in gen.glob("commands/*.py"):
        assert "--region" not in mod.read_text(encoding="utf-8")
    runtime_src = (gen / "runtime.py").read_text(encoding="utf-8")
    assert "resolve_connection" not in runtime_src
    assert "set_connection_overrides" not in runtime_src
    config_src = (gen / "config.py").read_text(encoding="utf-8")
    assert "resolve_connection" not in config_src
    assert "_CONN_FIELDS" not in config_src
