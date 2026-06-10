import importlib
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


def test_config_precedence(emitted, monkeypatch):
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.resolve("output", flag=None, default="table") == "table"
    (emitted / "cfg.yaml").write_text("output: json\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "_config_path", lambda: emitted / "cfg.yaml")
    assert cfg.resolve("output", flag=None, default="table") == "json"
    monkeypatch.setenv("FAKESDK_OUTPUT", "yaml")
    assert cfg.resolve("output", flag=None, default="table") == "yaml"
    assert cfg.resolve("output", flag="table", default="table") == "table"


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
    assert ": int = typer.Option(" in code           # required int (create)
    assert "Optional[bool] = typer.Option(None" in code  # optional bool


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
    assert 'rich_help_panel="Filter Options"' in show_fn   # --name (filter query param)
    assert 'rich_help_panel="Pagination Options"' in show_fn  # --limit + --all
    # --id (path) and --output are NOT panelled
    assert re.search(r'--id".*rich_help_panel', show_fn) is None
    assert re.search(r'--output".*rich_help_panel', show_fn) is None


def test_show_help_renders_panels(emitted, monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner
    main = importlib.import_module("fakesdk_cli.main")
    out = CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    assert "Filter Options" in out and "Pagination Options" in out
    assert "Options" in out   # main panel still present (--output/--help)


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
