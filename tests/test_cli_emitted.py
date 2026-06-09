import importlib
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


@pytest.fixture
def emitted(tmp_path):
    """Emit the fakesdk CLI into tmp_path, importable as `fakesdk_cli` (env_prefix FAKESDK)."""  # noqa: E501
    ir = build_cli_ir(introspect("fakesdk", FIXTURE), CliConfig())[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    sys.path.insert(0, str(tmp_path))
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    try:
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[name]


def test_config_precedence(emitted, monkeypatch):
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.resolve("output", flag=None, default="table") == "table"
    (emitted / "cfg.yaml").write_text("output: json\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "_config_path", lambda: emitted / "cfg.yaml")
    assert cfg.resolve("output", flag=None, default="table") == "json"
    monkeypatch.setenv("FAKESDK_OUTPUT", "yaml")
    assert cfg.resolve("output", flag=None, default="table") == "yaml"
    assert cfg.resolve("output", flag="table", default="table") == "table"
