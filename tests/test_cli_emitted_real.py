import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig, VariantMap
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

_APP_VARIANTS = VariantMap(
    path_param="type",
    map={
        "custom": "CustomApplicationInput",
        "private": "PrivateApplicationInput",
        "non-web": "NonWebApplicationInput",
        "localdesktopcustom": "LocalDesktopApplicationInput",
    },
)


@pytest.fixture
def real_cli(tmp_path):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
    cfg = CliConfig(variants={"applications.create_application": _APP_VARIANTS})
    ir, _ = build_cli_ir(inv, cfg)
    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path,
               env_prefix="PRISMA")
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]


def _patch_client(monkeypatch):
    import prisma_browser.extras.facade as facade
    mock = MagicMock(name="Client")
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: mock))
    return mock


def test_help_lists_verbs_and_objects(real_cli):
    from typer.testing import CliRunner
    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(main.app, ["--help"])
    assert res.exit_code == 0
    assert "set" in res.output and "show" in res.output and "del" in res.output
    res2 = CliRunner().invoke(main.app, ["show", "--help"])
    assert "application" in res2.output


def test_show_by_type_and_id_dispatch(real_cli, monkeypatch):
    from typer.testing import CliRunner
    mock = _patch_client(monkeypatch)
    # Give the mock a JSON-serializable return so the output renderer doesn't error.
    mock.applications.get_application_by_type_and_id.return_value = {
        "id": "APP-123", "type": "custom", "name": "Test App"
    }
    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(
        main.app,
        ["show", "application", "--type", "custom", "--id", "APP-123",
         "--output", "json"],
    )
    assert res.exit_code == 0, res.output
    # real facade: get_application_by_type_and_id(type="custom", id="APP-123")
    call = mock.applications.get_application_by_type_and_id
    assert call.called
    kwargs = call.call_args.kwargs
    assert kwargs.get("type") == "custom" and kwargs.get("id") == "APP-123"


def test_set_constructs_real_model(real_cli, monkeypatch):
    # Build a `set device-group` with the two required flat scalar fields: name (str)
    # and platform (DeviceGroupPlatform enum with value "Desktop Browser").
    # Asserts that the REAL DeviceGroupRequest model is constructed and passed to
    # create_device_group — proving model build + dispatch end-to-end.
    from prisma_browser.models.device_group_request import DeviceGroupRequest
    from typer.testing import CliRunner

    mock = _patch_client(monkeypatch)
    mock.device_groups.create_device_group.return_value = {
        "id": "DG-1", "name": "Kiosks", "platform": "Desktop Browser"
    }
    main = importlib.import_module("prisma_browser_cli.main")

    res = CliRunner().invoke(
        main.app,
        ["set", "device-group", "--name", "Kiosks",
         "--platform", "Desktop Browser", "--output", "json"],
    )
    assert res.exit_code == 0, res.output

    # find the create_device_group call on the mock and assert a real model was passed
    create_call = mock.device_groups.create_device_group
    assert create_call.called, "create_device_group was not called"
    call_kwargs = create_call.call_args.kwargs
    body = call_kwargs.get("device_group_request")
    assert body is not None, f"device_group_request kwarg missing; got: {call_kwargs}"
    assert isinstance(body, DeviceGroupRequest), (
        f"Expected DeviceGroupRequest, got {type(body)}"
    )
    assert body.name == "Kiosks"


def test_set_application_variant_constructs_wrapped_body(real_cli, monkeypatch):
    import prisma_browser.models as models
    from typer.testing import CliRunner

    mock = _patch_client(monkeypatch)
    mock.applications.create_application.return_value = {
        "id": "APP-1", "type": "custom", "name": "MyApp"
    }
    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(
        main.app,
        ["set", "application", "custom", "--name", "MyApp",
         "--urls", '[{"url": "https://example.com"}]', "--output", "json"],
    )
    assert res.exit_code == 0, res.output
    call = mock.applications.create_application
    assert call.called
    kwargs = call.call_args.kwargs
    assert kwargs.get("type") == "custom"                       # top-level path param
    body = kwargs.get("create_or_replace_app_input")
    assert isinstance(body, models.CreateOrReplaceAppInput)      # wrapped (H3)
    inner = body.actual_instance
    assert isinstance(inner, models.CustomApplicationInput)
    assert inner.type == "custom"  # discriminator injected into body
    assert inner.name == "MyApp"


def test_real_cli_build_emits_full_project(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    import phantasos.cli as climod
    from phantasos.cli import main

    # LoadedProduct is a plain (non-frozen) dataclass — redirect output_dir into
    # tmp_path so the build does NOT write the real ../prisma-browser-sdk tree.
    # cli build computes: out_dir = Path(loaded.output_dir).parent / f"{package}-cli"
    # so setting output_dir = tmp_path / "prisma-browser-sdk" gives
    # out_dir = tmp_path / "prisma_browser-cli" (package name uses underscore).
    real = climod.load_product("prisma-browser")
    real.output_dir = tmp_path / "prisma-browser-sdk"
    monkeypatch.setattr(climod, "load_product", lambda name: real)

    # Ensure prisma_browser is importable: introspect() inserts sdk_path into sys.path,
    # but tmp_path/prisma-browser-sdk is empty; make the real SDK importable first.
    if str(REAL_SDK) not in sys.path:
        sys.path.insert(0, str(REAL_SDK))

    rc = main(["cli", "build", "prisma-browser"])
    assert rc == 0
    # out_dir = tmp_path.parent/prisma_browser-cli would be wrong;
    # since output_dir = tmp_path/"prisma-browser-sdk", parent = tmp_path,
    # and package = "prisma_browser", so out_dir = tmp_path/"prisma_browser-cli".
    root = tmp_path / "prisma_browser-cli"

    pyproject = (root / "pyproject.toml").read_text()
    assert "prisma-browser-sdk" in pyproject               # SDK distribution dep
    assert "prisma-browser-cli = " in pyproject             # console-script
    assert "[tool.uv.sources]" in pyproject
    assert 'path = "../prisma-browser-sdk", editable = true' in pyproject

    # project shell (render_scaffold)
    assert (root / "README.md").exists()
    assert (root / "noxfile.py").exists()
    assert (root / ".github" / "workflows" / "ci.yml").exists()
    env_example = (root / ".env.example").read_text()
    assert "SCOPE=" in env_example and "PRISMA_SASE_BASE_URL=" in env_example

    # package code (render_cli)
    assert (root / "prisma_browser_cli" / "_generated" / "app.py").exists()
    assert (root / "prisma_browser_cli" / "main.py").exists()

    # SDK component tests did NOT render for the CLI
    assert not (root / "tests" / "test_auth.py").exists()
    # the CLI smoke test + conftest DID render (from cli_overrides)
    assert (root / "tests" / "test_cli_smoke.py").exists()


def test_real_cli_yml_loads_project_and_variants():
    """Phase 3a: the authored products/prisma-browser/cli.yml is valid + complete."""
    from phantasos.generator.cli.cliconfig import load_cli_config

    cfg = load_cli_config(Path("products/prisma-browser/cli.yml"))
    assert cfg.project is not None
    assert cfg.project.distribution == "prisma-browser-cli"
    # both application write methods are variant-mapped (create + patch)
    assert "applications.create_application" in cfg.variants
    assert "applications.patch_application_by_type_and_id" in cfg.variants
    assert set(cfg.variants["applications.create_application"].map) == {
        "custom", "private", "non-web", "localdesktopcustom"}
    # the 16 non-CRUD ops are reserved under request (so the build warns about none)
    assert len(cfg.request) == 16
    assert cfg.request["devices.suspend_devices"].action == "suspend"


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_real_cli_yml_produces_variant_commands_and_no_unmapped():
    """Phase 3a: building with the real cli.yml fans applications into variant commands
    (each aggregating create + patch) and leaves nothing unmapped."""
    from phantasos.generator.cli.cliconfig import load_cli_config

    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"SDK runtime deps unavailable: {exc}")
    cfg = load_cli_config(Path("products/prisma-browser/cli.yml"))
    ir, unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}

    assert unmapped == []  # all non-CRUD ops reserved in request:
    custom = by_key["set:application:custom"]
    sub_verbs = {b.sub_verb for b in custom.bindings}
    assert sub_verbs == {"create", "patch"}  # variant aggregates both write methods
    # the create binding wraps the variant in the oneOf wrapper; patch in PatchAppInput
    create = next(b for b in custom.bindings if b.sub_verb == "create")
    patch = next(b for b in custom.bindings if b.sub_verb == "patch")
    assert create.body_model == "CustomApplicationInput"
    assert create.body_wrapper == "CreateOrReplaceAppInput"
    assert patch.body_model == "CustomPatchApplicationInput"
    assert patch.body_wrapper == "PatchAppInput"
    assert {"set:application:private", "set:application:non-web",
            "set:application:localdesktopcustom"} <= set(by_key)
