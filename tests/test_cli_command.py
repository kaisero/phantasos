from pathlib import Path

from phantasos.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_cli_discover_prints_table(capsys, monkeypatch):
    # Stub load_product so the command resolves package + sdk path to the fixture.
    import phantasos.cli as climod

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = FIXTURE

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "discover", "fakesdk"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "set widget" in out
    assert "UNMAPPED" in out


def test_cli_build_emits_project(tmp_path, monkeypatch):
    import phantasos.cli as climod

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-sdk"  # SDK dir; CLI emits to a sibling

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "build", "fakesdk"])
    assert rc == 0
    # CLI emitted to sibling `<sdk-parent>/<sdk_package>-cli/`
    cli_root = tmp_path / "fakesdk-cli"
    assert (cli_root / "fakesdk_cli" / "_generated" / "app.py").exists()
    assert (cli_root / "pyproject.toml").exists()
