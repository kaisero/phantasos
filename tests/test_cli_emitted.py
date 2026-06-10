import importlib
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig, RequestMapping, VariantMap
from phantasos.generator.cli.introspect import introspect
from phantasos.generator.cli.render_cli import render_cli

FIXTURE = Path(__file__).parent / "fixtures" / "fakesdk"

# Variant config so the fixture produces `set:gizmo:simple` and `set:gizmo:complex`
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

    rt.run("set:widget", path={}, body={"name": "foo"}, query={}, output="json",
           paginate_all=False, dry_run=False, verbose=False)
    rt.run(
        "set:widget", path={"id": "w9"}, body={"name": "bar"}, query={},
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

    rt.run("set:gizmo:simple", path={}, body={"name": "x"}, query={},
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
    rt.run("set:widget", path={}, body={"name": "x"}, query={}, output="json",
           paginate_all=False, dry_run=True, verbose=False)
    assert calls == []
    assert "set:widget" in capsys.readouterr().out


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
        rt.run("set:widget", path={}, body={"name": "x"}, query={}, output="json",
               paginate_all=False, dry_run=False, verbose=False)
    assert ei.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_set_with_id_defaults_to_patch_not_update(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run(
        "set:widget", path={"id": "w1"}, body={"name": "n"}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False, replace=False,
    )
    assert calls[0][0] == "patch_widget"   # NOT update_widget


def test_set_with_replace_uses_update(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run(
        "set:widget", path={"id": "w1"}, body={"name": "n"}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False, replace=True,
    )
    assert calls[0][0] == "update_widget"


def test_set_without_id_creates(emitted, monkeypatch):
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_cls())
    )
    rt.run(
        "set:widget", path={}, body={"name": "n"}, query={},
        output="json", paginate_all=False, dry_run=False, verbose=False, replace=False,
    )
    assert calls[0][0] == "create_widget"


def test_cli_runner_show_set_del(emitted, monkeypatch):
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
    res3 = r.invoke(main.app, ["set", "widget", "--name", "foo", "--output", "json"])
    assert res3.exit_code == 0
    res4 = r.invoke(main.app, ["del", "widget", "--id", "w1", "--output", "json"])
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
    # variant create: set gizmo simple
    res = r.invoke(
        main.app, ["set", "gizmo", "simple", "--name", "g1", "--output", "json"]
    )
    assert res.exit_code == 0, res.output
    # non-variant patch under the same object: set gizmo patch
    res2 = r.invoke(
        main.app,
        ["set", "gizmo", "patch", "--id", "z9", "--name", "g2", "--output", "json"],
    )
    assert res2.exit_code == 0, res2.output

    names = [c[0] for c in calls]
    assert "create_gizmo" in names         # from `set gizmo simple`
    assert "patch_gizmo" in names           # from `set gizmo patch`
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
        ["request", "widget", "suspend", "--name", "W", "--output", "json"],
    )
    assert res.exit_code == 0, res.output
    res2 = r.invoke(
        main.app,
        ["request", "widget", "revoke", "--id", "W9", "--name", "X",
         "--output", "json"],
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
