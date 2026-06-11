import importlib
import re
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping, VariantMap
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"

# Variant config so the fixture produces `create:gizmo:simple` and `create:gizmo:complex`  # noqa: E501
_FAKESDK_CLI_CONFIG = CliConfig(
    variants={
        "gizmos.create_gizmo": VariantMap(
            path_param="type",
            map={"simple": "SimpleGizmoInput", "complex": "ComplexGizmoInput"},
        )
    },
    request={
        "widgets.suspend_widget": RequestMapping(object="widget", action="suspend"),
        "widgets.revoke_widget": RequestMapping(object="widget", action="revoke"),
    },
    defaults={"widgets.list_widgets": {"name": "gadget", "limit": 50}},
)


@pytest.fixture
def emitted(tmp_path):
    """Emit the fakesdk CLI into tmp_path, importable as `fakesdk_cli` (env_prefix FAKESDK)."""  # noqa: E501
    ir = build_cli_ir(introspect("fakesdk", FIXTURE), _FAKESDK_CLI_CONFIG)[0]
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


def test_output_formats(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode="python"):
            return {"id": "a1", "name": "slack", "nested": {"x": 1}}

    out.render(_Model(), fmt="json")
    assert '"name"' in capsys.readouterr().out  # json includes name

    out.render([_Model()], fmt="yaml")
    assert "name: slack" in capsys.readouterr().out

    out.render([_Model()], fmt="table")
    table = capsys.readouterr().out
    assert "id" in table and "name" in table and "a1" in table
    assert "nested" not in table  # dict columns are dropped from the table view


def _write_user_config(home, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def test_config_defaults_when_no_user_file(emitted, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    c = cfg.get()
    assert c.pager.enabled is False
    assert c.pager.command is None
    assert c.output.format == "json"
    assert cfg.load_config()[1] == ()  # no warnings
    assert cfg.load_config()[2] == ("packaged defaults",)
    assert cfg.default_output() == "json"


def test_config_packaged_defaults_match_models(emitted):
    import yaml as _yaml
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    data = _yaml.safe_load(cfg.packaged_default_text())
    assert cfg.ConfigFile.model_validate(data) == cfg.ConfigFile()


def test_config_homedir_override_and_env_precedence(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    _write_user_config(
        home,
        "configuration:\n  output:\n    format: table\n  pager:\n    enabled: true\n",
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "table"
    assert cfg.get().pager.enabled is True
    assert str(home / ".fakesdk_cli" / "config.yml") in cfg.load_config()[2]
    # env beats file (clear the cache after mutating the environment)
    monkeypatch.setenv("FAKESDK_OUTPUT_FORMAT", "yaml")
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "off")
    cfg.load_config.cache_clear()
    assert cfg.get().output.format == "yaml"
    assert cfg.get().pager.enabled is False
    assert "environment variables" in cfg.load_config()[2]
    # env passthrough for the command field
    monkeypatch.setenv("FAKESDK_PAGER_COMMAND", "bat -p")
    cfg.load_config.cache_clear()
    assert cfg.get().pager.command == "bat -p"


def test_config_unknown_key_warns_once(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pagre:\n    enabled: true\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.get()
    cfg.get()  # second call must not re-warn
    err = capsys.readouterr().err
    assert err.count("unknown config key 'configuration.pagre'") == 1


def test_config_wrong_type_falls_back(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pager:\n    enabled: maybe\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False  # default applied
    err = capsys.readouterr().err
    assert "configuration.pager.enabled" in err and "default" in err


def test_config_malformed_yaml_ignores_file(emitted, monkeypatch, tmp_path, capsys):
    home = tmp_path / "home"
    _write_user_config(home, ":: this is not yaml ::\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "json"  # defaults survive
    assert "invalid YAML" in capsys.readouterr().err


def test_config_unreadable_file_warns_and_continues(
    emitted, monkeypatch, tmp_path, capsys
):
    import os as _os
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: table\n")
    cfg_file = home / ".fakesdk_cli" / "config.yml"
    cfg_file.chmod(0o000)
    if _os.access(cfg_file, _os.R_OK):  # running as root: permission bits ineffective
        pytest.skip("cannot make file unreadable (running as privileged user)")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "json"  # defaults survive
    assert "unreadable" in capsys.readouterr().err


def test_config_bad_bool_env_ignored(emitted, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "banana")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False
    assert "not a boolean" in capsys.readouterr().err


def _fake_client(recorder):
    """A stand-in matching the fixture facade shape; records calls into `recorder`."""
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name):
            def _call(**kw):
                recorder.append((name, kw))
                return {"id": kw.get("id", "new")}
            return _call

    class _FakeClientCls:
        widgets = _Rec()
        gizmos = _Rec()
        things = _Rec()

        def paginate(self, method, **kw):
            return iter(method(**kw) or [])

    return facade, _FakeClientCls


def test_runtime_create_vs_patch(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )

    rt.run("create:widget", path={}, body={"name": "foo", "priority": 1}, query={},
           output="json", paginate_all=False, dry_run=False, verbose=False)
    rt.run(
        "update:widget", path={"id": "w9"}, body={"name": "bar"}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False,
    )
    assert calls[0][0] == "create_widget"
    assert calls[1][0] == "patch_widget" and calls[1][1].get("id") == "w9"


def test_runtime_variant_wraps_body_and_fills_type(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.models as models
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )

    rt.run("create:gizmo:simple", path={}, body={"name": "x"}, query={},
           output="json", paginate_all=False, dry_run=False, verbose=False)
    name, kw = calls[0]
    assert name == "create_gizmo"
    assert kw["type"] == "simple"  # H4: variant fills the path param
    wrapped = kw["create_gizmo_input"]
    assert isinstance(wrapped, models.CreateGizmoInput)  # H3: oneOf wrapper
    assert isinstance(wrapped.actual_instance, models.SimpleGizmoInput)
    assert wrapped.actual_instance.name == "x"


def test_runtime_dry_run_does_not_call(emitted, monkeypatch, capsys):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run("create:widget", path={}, body={"name": "x", "priority": 1}, query={},
           output="json", paginate_all=False, dry_run=True, verbose=False)
    assert calls == []
    assert "create:widget" in capsys.readouterr().out


def test_runtime_friendly_error_on_sdk_exception(emitted, monkeypatch, capsys):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.exceptions as exc_mod
    import fakesdk.extras.facade as facade

    class _Boom:
        widgets = None

        def __init__(self):
            class _W:
                def create_widget(self, **kw):
                    raise exc_mod.OpenApiException("boom")
            self.widgets = _W()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Boom()))
    import pytest as _pytest
    with _pytest.raises(SystemExit) as ei:
        rt.run("create:widget", path={}, body={"name": "x", "priority": 1}, query={},
               output="json", paginate_all=False, dry_run=False, verbose=False)
    assert ei.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_update_uses_patch(emitted, monkeypatch):
    # `update X --id` dispatches to the PATCH binding (PUT update_* is deferred).
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run(
        "update:widget", path={"id": "w1"}, body={"name": "n"}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False,
    )
    assert calls[0][0] == "patch_widget"   # NOT update_widget (PUT deferred)


def test_create_without_id_creates(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run(
        "create:widget", path={}, body={"name": "n", "priority": 1}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False,
    )
    assert calls[0][0] == "create_widget"


def test_cli_runner_show_create_delete(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    import fakesdk.extras.facade as facade
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    r = CliRunner()
    res1 = r.invoke(main.app, ["show", "widget", "--output", "json"])
    assert res1.exit_code == 0
    res2 = r.invoke(main.app, ["show", "widget", "--id", "w1", "--output", "json"])
    assert res2.exit_code == 0
    res3 = r.invoke(
        main.app,
        ["create", "widget", "--name", "foo", "--priority", "1", "--output", "json"],
    )
    assert res3.exit_code == 0
    res4 = r.invoke(main.app, ["delete", "widget", "--id", "w1", "--output", "json"])
    assert res4.exit_code == 0

    kinds = [c[0] for c in calls]
    assert "list_widgets" in kinds and "get_widget_by_id" in kinds
    assert "create_widget" in kinds and "delete_widget_by_id" in kinds


def test_cli_runner_variant_and_nonvariant_under_object(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    import fakesdk.models as models

    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    r = CliRunner()
    # variant create: create gizmo simple (create_gizmo is variant-mapped)
    res = r.invoke(
        main.app, ["create", "gizmo", "simple", "--name", "g1", "--output", "json"]
    )
    assert res.exit_code == 0, res.output
    # non-variant patch under the update verb: update gizmo (patch_gizmo, no variant)
    res2 = r.invoke(
        main.app,
        ["update", "gizmo", "--id", "z9", "--name", "g2", "--output", "json"],
    )
    assert res2.exit_code == 0, res2.output

    names = [c[0] for c in calls]
    assert "create_gizmo" in names         # from `create gizmo simple`
    assert "patch_gizmo" in names           # from `update gizmo`
    create_call = next(kw for n, kw in calls if n == "create_gizmo")
    assert create_call["type"] == "simple"
    assert isinstance(create_call["create_gizmo_input"], models.CreateGizmoInput)


def test_runtime_coerces_int_query(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app, ["show", "widget", "--limit", "50", "--output", "json"]
    )
    assert res.exit_code == 0, res.output
    _, kw = next((n, k) for n, k in calls if n == "list_widgets")
    assert kw.get("limit") == 50 and isinstance(kw["limit"], int)  # coerced str->int


def test_cli_runner_request_actions(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    r = CliRunner()
    # request is a verb group
    assert "request" in r.invoke(main.app, ["--help"]).output
    res = r.invoke(
        main.app,
        ["request", "widget", "suspend", "--name", "W", "--priority", "1",
         "--output", "json"],
    )
    assert res.exit_code == 0, res.output
    res2 = r.invoke(
        main.app,
        ["request", "widget", "revoke", "--id", "W9", "--name", "X",
         "--priority", "1", "--output", "json"],
    )
    assert res2.exit_code == 0, res2.output

    names = [c[0] for c in calls]
    assert "suspend_widget" in names
    assert "revoke_widget" in names
    revoke_call = next(kw for n, kw in calls if n == "revoke_widget")
    assert revoke_call.get("id") == "W9"


def test_output_defaults_to_json_not_table(emitted, monkeypatch):
    import contextlib
    import io

    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode="python"):
            return {"id": "a1", "name": "slack"}

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out.render(_Model())          # no fmt → default
    text = buf.getvalue()
    assert '"id"' in text and '"name"' in text   # JSON, not a table or repr
    assert "_Model(" not in text                  # no python repr


def test_to_data_never_leaks_repr(emitted):
    import contextlib
    import io

    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Weird:  # no model_dump, not a scalar/dict/list
        def __repr__(self):
            return "<_Weird object at 0xdeadbeef>"

    data = out._to_data(_Weird())
    assert isinstance(data, str)  # converted, not passed through raw
    # render(json) must not crash and must not emit the angle-bracket repr as an object
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out.render(_Weird(), fmt="json")
    assert buf.getvalue().strip()                 # produced some JSON string output


def test_cli_runner_show_defaults_to_json(emitted, monkeypatch):
    import fakesdk.extras.facade as facade
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")

    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])  # NO --output
    assert res.exit_code == 0, res.output
    assert '"id"' in res.output                   # default JSON output
    assert "WidgetsApi" not in res.output and "object at 0x" not in res.output


def test_env_file_is_auto_loaded(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    # a .env in the CWD the user runs from
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / ".env").write_text("DEMO_TOKEN=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("DEMO_TOKEN", raising=False)

    seen: dict = {}

    class _Rec:
        def __getattr__(self, name):
            def _call(**kw):
                return []
            return _call

    class _Client:
        widgets = _Rec()
        def paginate(self, m, **kw):
            return iter([])

    def _from_env(cls):
        import os
        # was .env loaded before from_env?
        seen["DEMO_TOKEN"] = os.environ.get("DEMO_TOKEN")
        return _Client()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(_from_env))

    res = CliRunner().invoke(main.app, ["show", "widget", "--output", "json"])
    assert res.exit_code == 0, res.output
    # _client() called load_dotenv() before from_env()
    assert seen["DEMO_TOKEN"] == "from-dotenv"


def test_create_missing_required_errors_cleanly(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])  # missing required --name
    assert res.exit_code != 0 and (
        "Missing option" in res.output or "required" in res.output.lower()
    )


def test_update_requires_id(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--name", "x"])   # no --id
    assert res.exit_code != 0
    assert "--id" in res.output or "id" in res.output.lower()


def test_update_body_fields_optional(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app, ["update", "widget", "--id", "w1", "--output", "json"]
    )
    assert res.exit_code == 0, res.output           # no required body flags
    assert any(n == "patch_widget" for n, _ in calls)


def test_delete_requires_id(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["delete", "widget"])   # no --id
    assert res.exit_code != 0


def test_scalar_body_flags_use_real_types(emitted, tmp_path):
    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.introspect import introspect
    from phantasos.generator.cli.render_cli import render_cli

    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, CliConfig())
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path)
    code = (
        tmp_path / "fakesdk_cli" / "_generated" / "commands" / "widgets.py"
    ).read_text()
    # Scalar body flags get their REAL Python types (not bare str). Required ->
    # the bare scalar; optional -> the modern ``X | None`` union (matching what
    # ruff's UP rules emit, so no dangling Optional import). Assert the type
    # annotations appear; the exact `typer.Option(...)` layout is left to ruff
    # format. (Behavioral validation lives in test_scalar_type_validated_by_typer.)
    assert ": int = typer.Option(" in code           # required int (create)
    assert "priority: int" in code                    # priority typed as int
    assert "bool | None = typer.Option(None" in code  # optional bool


def test_scalar_type_validated_by_typer(emitted, monkeypatch):
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "abc"],
    )
    assert res.exit_code != 0  # 'abc' is not a valid int -> Typer rejects


def test_enum_flag_lists_choices_in_help(emitted):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    h = CliRunner().invoke(main.app, ["create", "widget", "--help"]).output
    assert "values:" in h.lower()
    assert "red" in h.lower()        # a real Color choice (red/blue in the fixture)


def test_enum_flag_accepts_unlisted_value(emitted, monkeypatch):
    # permissive: SDK is LenientStrEnum -> unknown enum value ACCEPTED, not rejected
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    calls = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1",
         "--color", "chartreuse", "--output", "json"],
    )
    assert res.exit_code == 0, res.output       # unlisted value passes through


def test_error_headline_extraction(emitted):
    out = importlib.import_module("fakesdk_cli._generated.output")
    # prisma-style nested envelope -> the specific `error` field
    assert out._error_headline(
        {"errorResponse": {"error": "group name already exists",
                           "message": "failed to create device group"}}
    ) == "group name already exists"
    # flat message
    assert out._error_headline({"message": "boom"}) == "boom"
    # RFC7807-ish: detail preferred over title
    assert out._error_headline(
        {"title": "Bad Request", "detail": "x out of range"}
    ) == "x out of range"
    # error-as-object
    assert out._error_headline({"error": {"message": "nested"}}) == "nested"
    # nothing usable
    assert out._error_headline({"foo": 1}) is None
    assert out._error_headline("not a dict") is None


def test_render_error_api_exception_to_stderr(emitted, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Exc:                      # duck-typed ApiException
        status = 400
        reason = "Bad Request"
        body = (
            '{"errorResponse":{"error":"group name already exists",'
            '"message":"failed to create device group"}}'
        )
        data = None
    out.render_error(_Exc())
    err = capsys.readouterr().err
    assert "Error 400 Bad Request" in err
    assert "group name already exists" in err           # headline
    assert "errorResponse" in err and "failed to create device group" in err  # body
    assert "HTTPHeaderDict" not in err  # noise gone
    assert "response headers" not in err.lower()


def test_render_error_non_api(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render_error(ValueError("bad --flag value"))
    err = capsys.readouterr().err
    assert "error: bad --flag value" in err


def test_cli_runner_api_error_is_pretty(emitted, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.exceptions as fexc
    import fakesdk.extras.facade as facade

    class _Client:
        class widgets:  # noqa: N801
            @staticmethod
            def create_widget(**kw):
                raise fexc.ApiException(
                    status=400, reason="Bad Request",
                    body='{"errorResponse":{"error":"widget name already exists",'
                         '"message":"failed to create widget"}}')
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Client()))

    res = CliRunner().invoke(
        main.app, ["create", "widget", "--name", "dup", "--priority", "1"]
    )
    assert res.exit_code == 1, res.output
    assert "Error 400 Bad Request" in res.output
    assert "widget name already exists" in res.output          # headline
    assert "errorResponse" in res.output                        # full JSON body
    assert "HTTPHeaderDict" not in res.output
    assert "response headers" not in res.output.lower()


def test_render_error_non_json_body(emitted, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Exc:
        status = 502
        reason = "Bad Gateway"
        body = "upstream timeout"
        data = None
    out.render_error(_Exc())
    err = capsys.readouterr().err
    assert "Error 502 Bad Gateway" in err and "upstream timeout" in err


def test_render_none_is_silent(emitted, capsys):
    """A None result (e.g. delete / HTTP 204) prints nothing in any format."""
    out = importlib.import_module("fakesdk_cli._generated.output")
    for fmt in ("json", "yaml", "table"):
        out.render(None, fmt=fmt)
        captured = capsys.readouterr()
        assert captured.out == "", f"{fmt}: {captured.out!r}"
        assert captured.err == ""


def test_cli_runner_delete_silent_when_none(emitted, monkeypatch):
    """A delete whose SDK method returns None succeeds with NO stdout (no 'null')."""
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name):
            return lambda **kw: None        # SDK delete returns None (204)

    class _Client:
        def __getattr__(self, name):
            return _Rec()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Client()))
    res = CliRunner().invoke(main.app, ["delete", "widget", "--id", "w1"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == ""         # no "null", no output on success


def test_show_flags_grouped_into_panels(emitted, tmp_path):
    import re

    from phantasos.generator.cli.classify import build_cli_ir
    from phantasos.generator.cli.introspect import introspect
    from phantasos.generator.cli.render_cli import render_cli
    inv = introspect("fakesdk", FIXTURE)
    ir, _ = build_cli_ir(inv, _FAKESDK_CLI_CONFIG)
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path)
    code = (
        tmp_path / "fakesdk_cli" / "_generated" / "commands" / "widgets.py"
    ).read_text()
    show_fn = re.search(r"def show_widget\(.*?\n\) ->", code, re.S).group(0)
    assert 'rich_help_panel="Filters"' in show_fn   # --name (filter query param)
    assert 'rich_help_panel="Pagination"' in show_fn  # --limit + --all
    # --id (path) is NOT panelled; --output joined "Common" (2026-06-11)
    assert re.search(r'--id".*rich_help_panel', show_fn) is None
    assert re.search(r'--output", rich_help_panel="Common"', show_fn)


def test_show_help_renders_panels(emitted, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    out = CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    titles = _panel_titles(out)
    assert "Filters" in titles and "Pagination" in titles
    assert "Options" in titles  # default panel kept (domain flags + --help)


def test_render_dry_run_get_no_body(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render_dry_run("GET", "https://api.test/devices?limit=50", None)
    captured = capsys.readouterr().out
    assert "DRY RUN" in captured
    assert "GET" in captured and "https://api.test/devices?limit=50" in captured


def test_render_dry_run_post_with_body(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render_dry_run(
        "POST",
        "https://api.test/device-groups",
        {"name": "Kiosks", "platform": "Desktop Browser"},
    )
    captured = capsys.readouterr().out
    assert "POST" in captured and "device-groups" in captured
    assert '"name"' in captured and "Kiosks" in captured       # body JSON


def test_dry_run_falls_back_without_serialize(emitted, monkeypatch, capsys):
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    # create widget --dry-run: body is built (required fields by Typer), then
    # _dry_run tries fakesdk.api_client (absent) -> falls back to call-ref string.
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--dry-run"],
    )
    assert res.exit_code == 0, res.output
    assert "DRY-RUN create:widget" in res.output and "create_widget" in res.output


def test_version_flag_wired(emitted, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--version"])
    assert res.exit_code == 0, res.output
    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    assert app_mod._DISTRIBUTION in res.output            # distribution name printed
    # not installed in the tmp render -> graceful "unknown", no crash
    assert app_mod._resolve_version() in res.output


def test_version_resolves_from_metadata(emitted, monkeypatch):
    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    monkeypatch.setattr(app_mod._metadata, "version", lambda dist: "9.9.9")
    assert app_mod._resolve_version() == "9.9.9"


def _row(i):
    return {
        "id": f"w{i}", "name": f"widget-{i}", "priority": i, "enabled": True,
        "tags": ["a", "b", "c", "d", "e"],
        "spec": {"x": 1},
        "members": [{"name": "alice"}, {"name": "bob"}, {"name": "carol"},
                    {"name": "dave"}],
    }


def test_table_unwraps_list_envelope_and_uses_default_columns(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    envelope = {"page_info": {"cursor": None}, "data": [_row(1), _row(2)]}
    out.render(envelope, fmt="table",
               default_columns=[("id", "id"), ("name", "name")],
               items_field="data")
    text = capsys.readouterr().out
    assert "w1" in text and "widget-2" in text     # rows, not the envelope
    assert "page_info" not in text


def test_table_jmespath_columns_and_joined_preview(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render([_row(1)], fmt="table",
               columns=["name", "MEMBERS=members[].name", "tags"])
    text = capsys.readouterr().out
    assert "MEMBERS" in text
    assert "alice, bob, carol, +1 more" in text    # list-of-dicts preview via path
    assert "a, b, c, +2 more" in text              # scalar list preview


def test_table_cell_rendering_rules(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    row = {"id": "x", "gone": None, "flag": True, "nest": {"a": 1},
           "objs": [{"k": 1}, {"k": 2}]}
    out.render([row], fmt="table",
               columns=["id", "gone", "flag", "nest", "objs"])
    text = capsys.readouterr().out
    assert "true" in text                          # bools lowercase
    assert '{"a":1}' in text                       # dict -> compact json
    assert "2 items" in text                       # dicts w/o name/id -> count


def test_table_heuristic_fallback_when_no_columns(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    rows = [{"created": "t", "name": "n1", "id": "i1", "deep": {"x": 1},
             "a": 1, "b": 2, "c": 3, "d": 4}]
    out.render(rows, fmt="table")                  # no columns at all
    text = capsys.readouterr().out
    assert "id" in text and "name" in text         # preferred first
    assert "deep" not in text                      # nested excluded
    # cap 6: id, name, created, a, b, c -> "d" doesn't fit
    assert " d " not in text


def test_columns_split_and_header_parsing(emitted):
    out = importlib.import_module("fakesdk_cli._generated.output")
    specs = out.parse_columns(["id,OWNER=owner.name", "F=join(', ', tags)"])
    assert specs == [("id", "id"), ("OWNER", "owner.name"),
                     ("F", "join(', ', tags)")]    # comma inside () not split


def test_table_invalid_runtime_columns_exits_cleanly(emitted, capsys):
    import pytest

    out = importlib.import_module("fakesdk_cli._generated.output")
    with pytest.raises(SystemExit):
        out.render([{"id": "x"}], fmt="table", columns=["bad[expr"])
    assert "invalid --columns" in capsys.readouterr().err


def test_columns_flag_implies_table_and_renders_curated(emitted, monkeypatch, capsys):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(
        data=[models.Widget(id="w1", name="alpha", tags=["t1", "t2"]),
              models.Widget(id="w2", name="beta")]
    )

    class _W:
        def list_widgets(self, **kw):
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--columns", "name,id"])
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output and "w2" in res.output
    assert "page_info" not in res.output            # envelope unwrapped
    assert "{" not in res.output                     # table, not json


def test_show_without_columns_uses_ir_default_columns(emitted, monkeypatch):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(data=[models.Widget(id="w1", name="alpha")])

    class _W:
        def list_widgets(self, **kw):
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--output", "table"])
    assert res.exit_code == 0, res.output
    # ir default columns put id/name first and exclude the nested spec field
    assert "id" in res.output and "name" in res.output
    assert "spec" not in res.output


def test_fakesdk_generated_lint_clean(tmp_path):
    """Non-gated capstone: the fakesdk-rendered `_generated/` passes the scaffold's
    ruff config (E,F,I,UP,W; line-length 88) with ZERO errors. render_cli runs
    `ruff format` post-render, so the emitted code is already clean."""
    import shutil
    import subprocess
    ruff = shutil.which("ruff")
    if ruff is None:
        pytest.skip("ruff not on PATH")
    ir = build_cli_ir(introspect("fakesdk", FIXTURE), _FAKESDK_CLI_CONFIG)[0]
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path, env_prefix="FAKESDK")
    gen = tmp_path / "fakesdk_cli" / "_generated"
    res = subprocess.run(  # noqa: S603 — trusted `ruff` binary (shutil.which)
        [ruff, "check", "--isolated", "--select", "E,F,I,UP,W",
         "--line-length", "88", str(gen)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_query_default_is_injected_and_overridable(emitted, monkeypatch):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls = []

    class _W:
        def list_widgets(self, **kw):
            calls.append(kw)
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()

    # no flags -> cli.yml defaults flow into the SDK call (int correctly typed)
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}

    # user override wins
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--name", "other", "--limit", "7"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "other", "limit": 7}


def test_query_default_shown_in_help(emitted):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    res = CliRunner().invoke(app_mod.build_generated_app(),
                             ["show", "widget", "--help"])
    assert res.exit_code == 0
    assert "default:" in res.output and "gadget" in res.output


def test_injected_defaults_not_sent_to_get_binding(emitted, monkeypatch):
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls = []

    class _W:  # STRICT get signature, like the real SDK's @validate_call methods
        def get_widget_by_id(self, id, configuration_version=None):
            calls.append({"id": id, "configuration_version": configuration_version})
            return {"id": id, "name": "x"}

        def list_widgets(self, **kw):
            calls.append(kw)
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda: _Client())
    runner = CliRunner()

    # get binding: the injected name/limit defaults must NOT reach the call
    res = runner.invoke(app_mod.build_generated_app(),
                        ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"id": "w1", "configuration_version": None}

    # list binding still receives the defaults
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}


def test_model_body_defaults_still_not_rendered(emitted):
    """CRITICAL INVARIANT: pydantic model defaults (Flag.default) must never
    become CLI flag defaults — PATCH would silently send them. WidgetInput.mode
    defaults to 'fast' in the model; the emitted option must stay None."""
    import pathlib

    src = (pathlib.Path(emitted) / "fakesdk_cli" / "_generated" / "commands"
           / "widgets.py").read_text(encoding="utf-8")
    mode_lines = [ln for ln in src.splitlines() if '"--mode"' in ln]
    assert mode_lines, "expected a --mode option in the emitted widgets module"
    for line in mode_lines:
        assert '"fast"' not in line     # model default must NOT be rendered
        assert "None" in line           # option default stays None


def test_output_default_comes_from_config(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: yaml\n")
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0
    assert "id: w1" in res.output  # yaml rendering proves the config default applied

    # and --help shows the effective default
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "yaml" in res.output


def test_pager_flag_present_and_run_wires_it(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "--pager" in res.output and "--no-pager" in res.output

    out = importlib.import_module("fakesdk_cli._generated.output")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.extras.facade as facade

    calls: list = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    seen: list = []

    from contextlib import contextmanager

    @contextmanager
    def _spy(flag):
        seen.append(flag)
        yield

    monkeypatch.setattr(out, "maybe_paged", _spy)
    rt.run("show:widget", path={"id": "w1"}, body={}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False, pager=True)
    rt.run("show:widget", path={"id": "w1"}, body={}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False, pager=False)
    rt.run("show:widget", path={"id": "w1"}, body={}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False, pager=None)
    assert seen == [True, False, None]


def test_config_effective_dict_excludes_extras(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    _write_user_config(
        home, "configuration:\n  output:\n    format: table\n    extra_key: 1\n"
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    eff = cfg.effective_dict()
    assert eff["configuration"]["output"] == {"format": "table"}


def test_yaml_output_has_no_trailing_blank_line(emitted, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode="python"):
            return {"a": 1}

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert text.endswith("a: 1\n")
    assert not text.endswith("\n\n")


def test_autopager_short_content_writes_direct(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "10")
    monkeypatch.setenv("COLUMNS", "80")
    pager = out._AutoPager("/definitely/not/a/pager")
    pager.show("one\ntwo\nthree\n")  # 3 lines < 10 -> no spawn attempt
    captured = capsys.readouterr()
    assert "one\ntwo\nthree\n" in captured.out
    assert captured.err == ""  # no missing-binary warning -> nothing was spawned


def test_autopager_tall_content_pipes_to_command(emitted, monkeypatch, tmp_path):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "10")
    monkeypatch.setenv("COLUMNS", "80")
    sink = tmp_path / "paged.txt"
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager(f"tee {sink}").show(content)
    assert sink.read_text(encoding="utf-8") == content


def test_autopager_missing_binary_falls_back(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager("/definitely/not/a/pager").show(content)
    captured = capsys.readouterr()
    assert captured.out.endswith("line49\n")  # content not lost
    assert "pager command not found" in captured.err


def test_autopager_blank_command_falls_back(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager("   ").show(content)  # must not raise; content not lost
    assert capsys.readouterr().out.endswith("line49\n")


def test_pager_command_resolution(emitted, monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("PAGER", raising=False)
    out = importlib.import_module("fakesdk_cli._generated.output")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert out.pager_command() == "less -RFX"  # built-in fallback
    monkeypatch.setenv("PAGER", "mypager")
    assert out.pager_command() == "mypager"  # $PAGER beats fallback
    _write_user_config(
        home, "configuration:\n  pager:\n    command: bat --paging=always\n"
    )
    cfg.load_config.cache_clear()
    assert out.pager_command() == "bat --paging=always"  # config beats $PAGER


def test_maybe_paged_skips_when_not_a_tty(emitted, monkeypatch, capsys):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: False)
    with out.maybe_paged(True):
        out._console.print("hello")
    assert "hello" in capsys.readouterr().out  # rendered directly, no pager


def test_maybe_paged_uses_pager_when_tty(emitted, monkeypatch, tmp_path):
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: True)
    sink = tmp_path / "paged.txt"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with out.maybe_paged(True):
        for i in range(50):
            out._console.print(f"row{i}")
    assert "row49" in sink.read_text(encoding="utf-8")


def test_config_init_and_show_commands(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    res = r.invoke(main.app, ["config", "init"])
    assert res.exit_code == 0
    target = tmp_path / ".fakesdk_cli" / "config.yml"
    assert target.exists()
    assert "pager" in target.read_text(encoding="utf-8")  # commented defaults

    res = r.invoke(main.app, ["config", "init"])
    assert res.exit_code == 1  # refuses without --force

    target.write_text("STALE SENTINEL\n", encoding="utf-8")
    res = r.invoke(main.app, ["config", "init", "--force"])
    assert res.exit_code == 0
    assert "STALE SENTINEL" not in target.read_text(encoding="utf-8")

    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "merged from" in res.output
    assert str(target) in res.output  # homedir file listed as a source
    assert "format: json" in res.output


def test_config_group_in_its_own_help_panel(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--help"])
    assert res.exit_code == 0
    assert "config" in res.output
    # "CLI" must render as a dedicated panel TITLE (box header), not merely as a
    # word in help text — this fails if rich_help_panel="CLI" is dropped.
    assert any(
        "CLI" in line and "─" in line for line in res.output.splitlines()
    )


_PANEL_RE = re.compile(r"╭─+\s(.+?)\s─+╮")


def _panel_titles(help_output: str) -> list[str]:
    """Rich panel titles in render order from a --help screen."""
    titles = []
    for line in help_output.splitlines():
        m = _PANEL_RE.search(line)
        if m:
            titles.append(m.group(1).strip())
    return titles


def test_common_options_panel_renders_last(emitted, monkeypatch, tmp_path):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert res.exit_code == 0
    titles = _panel_titles(res.output)
    assert "Common" in titles
    assert titles[-1] == "Common"  # the lowest container
    # the five members appear after the Common header...
    idx = res.output.index("Common")
    tail = res.output[idx:]
    for flag in ("--output", "--columns", "--dry-run", "--verbose", "--pager"):
        assert flag in tail
    # ...and the domain flag stays in the default Options panel above it
    assert "--id" in res.output[:idx]
    # --help remains stock (default panel, i.e. before Common)
    assert "--help" in res.output[:idx]


def test_pagination_panel_precedes_common_on_non_list_commands(
    emitted, monkeypatch, tmp_path
):
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    # create has NO pagination query params; --all alone must still anchor the
    # Pagination panel BEFORE Common (the declaration-reorder fix)
    res = CliRunner().invoke(main.app, ["create", "widget", "--help"])
    assert res.exit_code == 0
    titles = _panel_titles(res.output)
    assert titles[-1] == "Common"
    assert "Pagination" in titles
    assert titles.index("Pagination") < titles.index("Common")
