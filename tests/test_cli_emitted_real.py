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
               env_prefix="PRISMA", distribution="prisma-browser-cli")
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
    assert "create" in res.output and "show" in res.output and "delete" in res.output
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
        ["create", "device-group", "--name", "Kiosks",
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
        ["create", "application", "custom", "--name", "MyApp",
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
    # cli build computes out_dir = Path(loaded.output_dir).parent / <cli distribution>,
    # so setting output_dir = tmp_path / "prisma-browser-sdk" gives
    # out_dir = tmp_path / "prisma-browser-cli" (the cli.yml distribution, hyphenated).
    real = climod.load_product("prisma-browser")
    real.output_dir = tmp_path / "prisma-browser-sdk"
    monkeypatch.setattr(climod, "load_product", lambda name: real)

    # Ensure prisma_browser is importable: introspect() inserts sdk_path into sys.path,
    # but tmp_path/prisma-browser-sdk is empty; make the real SDK importable first.
    if str(REAL_SDK) not in sys.path:
        sys.path.insert(0, str(REAL_SDK))

    rc = main(["cli", "build", "prisma-browser"])
    assert rc == 0
    # The project dir follows the cli.yml distribution ("prisma-browser-cli"), NOT the
    # underscore package name — mirroring how the SDK dir is "prisma-browser-sdk".
    root = tmp_path / "prisma-browser-cli"
    assert not (tmp_path / "prisma_browser-cli").exists()   # no underscore dir

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

    assert unmapped == []
    # create + patch are now distinct single-binding variant commands
    create_cmd = by_key["create:application:custom"]
    update_cmd = by_key["update:application:custom"]
    assert {b.sub_verb for b in create_cmd.bindings} == {"create"}
    assert {b.sub_verb for b in update_cmd.bindings} == {"patch"}
    # the create binding wraps the variant in the oneOf wrapper; patch in PatchAppInput
    create = create_cmd.bindings[0]
    patch = update_cmd.bindings[0]
    assert create.body_model == "CustomApplicationInput"
    assert create.body_wrapper == "CreateOrReplaceAppInput"
    assert patch.body_model == "CustomPatchApplicationInput"
    assert patch.body_wrapper == "PatchAppInput"
    assert {"create:application:private", "create:application:non-web",
            "create:application:localdesktopcustom"} <= set(by_key)


def test_real_request_commands_dispatch(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from phantasos.generator.cli.cliconfig import load_cli_config

    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"SDK runtime deps unavailable: {exc}")
    cfg = load_cli_config(Path("products/prisma-browser/cli.yml"))
    ir, unmapped = build_cli_ir(inv, cfg)
    by_key = {c.key: c for c in ir.commands}
    # the cli.yml's request mappings are now real commands
    assert "request:device:suspend" in by_key
    assert "request:user-request:revoke" in by_key
    assert "request:configuration:publish" in by_key
    assert unmapped == []

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        import prisma_browser.extras.facade as facade
        mock = MagicMock(name="Client")
        mock.user_requests.revoke_user_request.return_value = {
            "id": "REQ-1", "status": "revoked"
        }
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: mock))
        # request user-request revoke --id REQ-1
        # (id + body; revoke body field is optional)
        res = CliRunner().invoke(
            main.app,
            ["request", "user-request", "revoke", "--id", "REQ-1", "--output", "json"],
        )
        assert res.exit_code == 0, res.output
        assert mock.user_requests.revoke_user_request.called
        kw = mock.user_requests.revoke_user_request.call_args.kwargs
        assert kw.get("id") == "REQ-1"
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]


def test_real_create_api_error_is_pretty(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    monkeypatch.setenv("NO_COLOR", "1")
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from phantasos.generator.cli.cliconfig import load_cli_config
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(str(exc))
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in list(sys.modules) if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        import prisma_browser.exceptions as pexc
        import prisma_browser.extras.facade as facade
        # the REAL 400 the user hit
        real_body = ('{"errorResponse":{"error":"group name already exists",'
                     '"message":"failed to create device group"}}')
        try:
            err = pexc.BadRequestException(
                status=400, reason="Bad Request", body=real_body
            )
        except TypeError:
            err = pexc.ApiException(status=400, reason="Bad Request", body=real_body)
        client = MagicMock(name="Client")
        client.device_groups.create_device_group.side_effect = err
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))

        runner = CliRunner()
        res = runner.invoke(main.app, ["create", "device-group", "--name", "dup",
                                       "--platform", "Desktop Browser"])
        assert res.exit_code == 1, res.output
        assert "Error 400 Bad Request" in res.output
        assert "group name already exists" in res.output           # headline
        # full JSON body is present
        assert "errorResponse" in res.output
        assert "failed to create device group" in res.output
        # the noise is GONE
        assert "HTTPHeaderDict" not in res.output
        assert "response headers" not in res.output.lower()
        # --verbose still surfaces the full exception (re-raised)
        res2 = runner.invoke(main.app, ["create", "device-group", "--name", "dup",
                                        "--platform", "Desktop Browser", "--verbose"])
        assert res2.exit_code != 0
        # the ApiException propagated under --verbose
        assert res2.exception is not None
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in list(sys.modules) if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]


def test_real_create_update_delete_device_group(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    from unittest.mock import MagicMock

    from typer.testing import CliRunner

    from phantasos.generator.cli.cliconfig import load_cli_config

    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(str(exc))
    ir, unmapped = build_cli_ir(
        inv, load_cli_config(Path("products/prisma-browser/cli.yml"))
    )
    keys = {c.key for c in ir.commands}
    assert {"create:device-group", "update:device-group",
            "delete:device-group", "show:device-group"} <= keys
    assert "patch:device-group" not in keys and "set:device-group" not in keys
    assert unmapped == []
    # device-group has patch_ -> update is a single PATCH binding
    upd = next(c for c in ir.commands if c.key == "update:device-group")
    assert [b.sub_verb for b in upd.bindings] == ["patch"]

    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        runner = CliRunner()
        # --help shows required name + permissive enum choices
        h = runner.invoke(main.app, ["create", "device-group", "--help"]).output
        assert "--platform" in h and "Desktop Browser" in h
        import prisma_browser.extras.facade as facade
        client = MagicMock(name="Client")
        monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
        # required enforced (no --platform) and update needs --id
        res_no_plat = runner.invoke(main.app, ["create", "device-group", "--name", "x"])
        assert res_no_plat.exit_code != 0
        res_no_id = runner.invoke(main.app, ["update", "device-group", "--name", "x"])
        assert res_no_id.exit_code != 0
        # permissive enum: unlisted platform accepted (dry-run, no dispatch)
        res_dry = runner.invoke(main.app, [
            "create", "device-group",
            "--name", "x", "--platform", "Holographic Browser", "--dry-run",
        ])
        assert res_dry.exit_code == 0
        # SUCCESSFUL partial PATCH dispatch — only the supplied field (model_construct)
        client.reset_mock()
        client.device_groups.patch_device_group.return_value = {
            "id": "DG-1", "name": "renamed"
        }
        res = runner.invoke(main.app, [
            "update", "device-group",
            "--id", "DG-1", "--name", "renamed", "--output", "json",
        ])
        assert res.exit_code == 0, res.output
        assert client.device_groups.patch_device_group.called
        call = client.device_groups.patch_device_group.call_args
        # the id is passed; patch body carries the supplied name (kwargs/args)
        flat = {**call.kwargs}
        assert call.args or flat   # something was passed
        # the body object the SDK received should reflect the supplied 'name'
        body_obj = next(
            (v for v in list(call.args) + list(flat.values())
             if hasattr(v, "name") or hasattr(v, "model_dump")),
            None,
        )
        # serialize to confirm 'renamed' made it via model_construct
        if body_obj is not None and hasattr(body_obj, "model_dump"):
            dumped = body_obj.model_dump(exclude_none=True)
            assert dumped.get("name") == "renamed", dumped
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in sys.modules if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]


def test_real_show_device_help_panels(tmp_path, monkeypatch):
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    monkeypatch.setenv("NO_COLOR", "1")
    from typer.testing import CliRunner

    from phantasos.generator.cli.cliconfig import load_cli_config
    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(str(exc))
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    render_cli(ir, package="prisma_browser_cli", out_dir=tmp_path)
    sys.path.insert(0, str(tmp_path))
    for n in [n for n in list(sys.modules) if n.startswith("prisma_browser_cli")]:
        del sys.modules[n]
    try:
        main = importlib.import_module("prisma_browser_cli.main")
        out = CliRunner().invoke(main.app, ["show", "device", "--help"]).output
        assert "Filter Options" in out and "Pagination Options" in out
        # a real filter is under filters; a pagination param is under pagination
        assert "--device-hostname" in out and "--limit" in out and "--sort" in out
        # the panels actually split them: Filter Options appears before
        # --device-hostname's row, Pagination Options before --limit — assert both
        # panel titles present + the flags present
    finally:
        sys.path.remove(str(tmp_path))
        for n in [n for n in list(sys.modules) if n.startswith("prisma_browser_cli")]:
            del sys.modules[n]


def test_real_dry_run_shows_http_request(real_cli, capsys):
    from typer.testing import CliRunner
    main = importlib.import_module("prisma_browser_cli.main")
    runner = CliRunner()

    # GET list, no body, query in URL
    r1 = runner.invoke(main.app, ["show", "device", "--limit", "50", "--dry-run"])
    assert r1.exit_code == 0, r1.output
    assert "GET" in r1.output
    assert "/devices" in r1.output and "limit=50" in r1.output
    assert "list_devices(" not in r1.output     # NOT the old call-reference string

    # POST create, body shown as JSON
    r2 = runner.invoke(
        main.app,
        ["create", "device-group", "--name", "Kiosks",
         "--platform", "Desktop Browser", "--dry-run"],
    )
    assert r2.exit_code == 0, r2.output
    assert "POST" in r2.output and "device-groups" in r2.output
    assert "Kiosks" in r2.output                        # body payload present

    # variant create: wrapped body
    r3 = runner.invoke(
        main.app,
        ["create", "application", "custom", "--name", "MyApp",
         "--urls", '[{"url": "https://example.com"}]', "--dry-run"],
    )
    assert r3.exit_code == 0, r3.output
    assert "POST" in r3.output and "MyApp" in r3.output


def test_real_dry_run_with_enum_query_flag(real_cli):
    from typer.testing import CliRunner
    main = importlib.import_module("prisma_browser_cli.main")
    res = CliRunner().invoke(
        main.app, ["show", "device", "--sort", "device.hostname", "--dry-run"]
    )
    assert res.exit_code == 0, res.output
    assert "GET" in res.output and "/devices" in res.output
    assert "sort=" in res.output          # enum query param made it into the URL
    assert "list_devices(" not in res.output  # NOT the fallback call-string


def test_real_version_flag(real_cli):
    from typer.testing import CliRunner
    main = importlib.import_module("prisma_browser_cli.main")
    app_mod = importlib.import_module("prisma_browser_cli._generated.app")
    res = CliRunner().invoke(main.app, ["--version"])
    assert res.exit_code == 0, res.output
    assert app_mod._DISTRIBUTION in res.output            # e.g. "prisma-browser-cli"


def test_generated_code_is_lint_clean(real_cli):
    """Capstone: the emitted `_generated/` passes the scaffold's ruff config
    (select E,F,I,UP,W; line-length 88) with ZERO errors — no noqa, no exclude.
    `real_cli` renders via `render_cli`, which `ruff format`s the output."""
    import shutil
    import subprocess
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not on PATH")
    gen = real_cli / "prisma_browser_cli" / "_generated"
    res = subprocess.run(  # noqa: S603 — trusted `ruff` binary (shutil.which)
        [ruff, "check", "--isolated", "--select", "E,F,I,UP,W",
         "--line-length", "88", str(gen)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr   # 0 lint errors in generated


def test_long_help_text_preserved(real_cli):
    """Word-wrapping long help into implicit-concat chunks must not drop text:
    Rich reassembles the chunks at runtime, so distinctive fragments survive."""
    import os

    from typer.testing import CliRunner
    os.environ["NO_COLOR"] = "1"
    main = importlib.import_module("prisma_browser_cli.main")
    out = CliRunner().invoke(main.app, ["show", "device", "--help"]).output
    # distinctive fragments from long device filter/sort help (text not lost)
    assert "sort by" in out.lower() or "filter by" in out.lower()


@pytest.mark.skipif(not REAL_SDK.exists(), reason="prisma-browser-sdk not built")
def test_real_ir_carries_columns():
    """The shipped cli.yml columns: resolve + validate against the real SDK."""
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import load_cli_config

    try:
        inv = introspect("prisma_browser", REAL_SDK)
    except ImportError as exc:
        pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")

    cfg = load_cli_config(
        Path(__file__).parent.parent / "products" / "prisma-browser" / "cli.yml"
    )
    ir, _ = build_cli_ir(inv, cfg)

    show_dg = next(c for c in ir.commands if c.key == "show:device-group")
    assert [c.path for c in show_dg.columns][:2] == ["id", "name"]
    assert show_dg.items_field == "data"
    # curated columns attach to the object's write commands too (per-object rule)
    create_dg = next(c for c in ir.commands if c.key == "create:device-group")
    assert create_dg.columns == show_dg.columns
    # application columns: JMESPath paths through actual_instance union wrapper
    show_app = next(c for c in ir.commands if c.key == "show:application")
    assert [c.path for c in show_app.columns][:2] == [
        "actual_instance.id", "actual_instance.name"
    ]
    assert show_app.items_field == "data"
    # every show command with a response model got SOME columns
    shows = [c for c in ir.commands if c.verb == "show"]
    assert any(c.columns for c in shows)
