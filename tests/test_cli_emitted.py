import importlib
import sys
from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_cli_ir
from phantasos.generator.cli.cliconfig import CliConfig, VariantMap
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
    }
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
