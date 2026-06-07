"""Unit tests for the sdkgen CLI (offline: generate is monkeypatched out)."""

import sys
from pathlib import Path

import pytest

import sdkgen
from sdkgen import cli, generate

_SPEC = """\
openapi: 3.0.0
info:
  title: Demo
  version: 1.2.3
paths:
  /things:
    get:
      operationId: listThings
      tags: [Things]
      responses:
        '200':
          description: ok
components:
  schemas:
    Thing:
      type: object
      properties:
        id:
          type: string
"""

_CONFIG_MODULE = """\
from sdkgen import Facade, SdkConfig

CONFIG = SdkConfig(
    spec="demo.yml",
    package="demo_cli",
    base_url="https://api.example.com",
    project_dir=PROJECT_DIR,
    auth=None,
    pagination=None,
    errors=None,
    facade=Facade(),
)
"""


def _write_fake_generated_pkg(project_dir: Path, pkgname: str) -> None:
    """Stand in for what OpenAPI Generator would emit (generate is mocked)."""
    pkg = project_dir / pkgname
    api = pkg / "api"
    models = pkg / "models"
    api.mkdir(parents=True)
    models.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (models / "__init__.py").write_text("", encoding="utf-8")
    (api / "__init__.py").write_text(
        f"from {pkgname}.api.things_api import ThingsApi\n", encoding="utf-8"
    )
    (api / "things_api.py").write_text(
        "class ThingsApi:\n    def list_things(self):\n        return []\n",
        encoding="utf-8",
    )


def test_cli_build_returns_zero_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_dir = tmp_path / "out"
    project_dir.mkdir()
    spec_path = tmp_path / "demo.yml"
    spec_path.write_text(_SPEC, encoding="utf-8")
    cfg_path = tmp_path / "demo_config.py"
    cfg_path.write_text(
        _CONFIG_MODULE.replace("PROJECT_DIR", repr(str(project_dir))),
        encoding="utf-8",
    )

    # generate() shells out to Java; replace it with the files it would have written.
    def fake_generate(
        spec_path: str, out_dir: str, package: str, library: str = "urllib3"
    ) -> None:
        _write_fake_generated_pkg(Path(out_dir), package)

    monkeypatch.setattr(generate, "generate", fake_generate)
    monkeypatch.setattr(sdkgen.generate, "generate", fake_generate)

    try:
        rc = cli.main(["build", str(cfg_path)])
    finally:
        for name in list(sys.modules):
            if name == "demo_cli" or name.startswith("demo_cli."):
                del sys.modules[name]
        sys.path[:] = [p for p in sys.path if p != str(project_dir)]

    assert rc == 0
    out = capsys.readouterr().out
    assert "built demo_cli" in out
    # provenance picked up the spec version
    about = (project_dir / "demo_cli" / "_about.py").read_text(encoding="utf-8")
    assert "1.2.3" in about
    assert "SPEC_VERSION = " in about
    # facade vendored
    assert (project_dir / "demo_cli" / "extras" / "facade.py").exists()


def test_cli_build_missing_config_returns_2() -> None:
    rc = cli.main(["build", "/no/such/config_module.py"])
    assert rc == 2
