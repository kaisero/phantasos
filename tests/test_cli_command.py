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
