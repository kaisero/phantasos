from pathlib import Path

import pytest

from phantasos.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"


def test_cli_discover_prints_table(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert "create widget" in out
    assert "UNMAPPED" in out


def test_cli_build_emits_full_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import phantasos.cli as climod

    sdk_ctx = {
        "package": "fakesdk",
        "library": "urllib3",
        "base_url": "http://x",
        "spec_version": "9.9.9",
        "spec_title": "FakeSDK",
        "has_auth": True,
        "has_pagination": False,
        "has_errors": False,
        "has_facade": True,
        "config_class_name": "Cfg",
        "distribution": "fakesdk-sdk",
        "description": "Fake SDK",
        "author": "A",
        "author_email": "a@x",
        "repo_url": "https://x",
        "license": "Apache-2.0",
        "python_versions": ["3.11", "3.12"],
        "dependencies": ["urllib3"],
    }

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
            project = object()  # non-None: metadata present in sdk_ctx

        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-sdk"
        context = sdk_ctx
        auth = type("A", (), {"scope_env": "SCOPE", "base_url_env": "FAKE_BASE_URL"})()
        errors = None  # no error component -> generic error envelope

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
    env_example = (root / ".env.example").read_text()
    assert "FAKE_BASE_URL=" in env_example  # auth-derived var, not just non-empty
    pyproject = (root / "pyproject.toml").read_text()
    assert "fakesdk-sdk" in pyproject  # SDK distribution dep (the fix)
    assert "fakesdk_cli.main:app" in pyproject  # console-script
    assert "typer" in pyproject
    assert "[tool.uv.sources]" in pyproject and 'path = "../fakesdk-sdk"' in pyproject
    # SDK component tests did NOT render for the CLI (has_auth forced False)
    assert not (root / "tests" / "test_auth.py").exists()


def test_cli_build_errors_without_project_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import phantasos.cli as climod

    _ctx = {"package": "fakesdk"}  # no project keys

    class _Loaded:
        class config:  # noqa: N801
            package = "fakesdk"
            project = None

        base_dir = FIXTURE
        output_dir = tmp_path / "fakesdk-sdk"
        context = _ctx
        auth = None

    monkeypatch.setattr(climod, "load_product", lambda name: _Loaded())
    # ensure no cli.yml project block is found
    rc = main(["cli", "build", "fakesdk"])
    assert rc == 2
