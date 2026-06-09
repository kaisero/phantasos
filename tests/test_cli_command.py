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


def test_cli_build_emits_full_project(tmp_path, monkeypatch):
    import phantasos.cli as climod

    sdk_ctx = {
        "package": "fakesdk", "library": "urllib3", "base_url": "http://x",
        "spec_version": "9.9.9", "spec_title": "FakeSDK",
        "has_auth": True, "has_pagination": False, "has_errors": False,
        "has_facade": True, "config_class_name": "Cfg",
        "distribution": "fakesdk-sdk", "description": "Fake SDK",
        "author": "A", "author_email": "a@x", "repo_url": "https://x",
        "license": "Apache-2.0", "python_versions": ["3.11", "3.12"],
        "dependencies": ["urllib3"],
    }

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-sdk"
        context = sdk_ctx
        auth = type("A", (), {"scope_env": "SCOPE", "base_url_env": "FAKE_BASE_URL"})()

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    rc = main(["cli", "build", "fakesdk"])
    assert rc == 0
    root = tmp_path / "fakesdk-cli"
    # package code (render_cli)
    assert (root / "fakesdk_cli" / "_generated" / "app.py").exists()
    assert (root / "fakesdk_cli" / "main.py").exists()
    # project shell (render_scaffold)
    assert (root / "README.md").exists()
    assert (root / "noxfile.py").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    assert (root / ".env.example").read_text().strip()  # non-empty (auth vars)
    pyproject = (root / "pyproject.toml").read_text()
    assert "fakesdk-sdk" in pyproject               # SDK distribution dep (the fix)
    assert "fakesdk_cli.main:app" in pyproject       # console-script
    assert "typer" in pyproject
    assert "[tool.uv.sources]" in pyproject and 'path = "../fakesdk-sdk"' in pyproject
    # SDK component tests did NOT render for the CLI (has_auth forced False)
    assert not (root / "tests" / "test_auth.py").exists()
