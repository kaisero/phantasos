import importlib
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from phantasos.config import ScmOAuth
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
def emitted(tmp_path: Path) -> Iterator[Path]:
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


@pytest.fixture
def pager_subprocess(tmp_path: Path) -> None:
    """Skip the test unless this environment can spawn a working pager
    subprocess in the test (pytest-capture) context.

    The autopager tests pipe content to a real `tee` subprocess. Some sandboxed
    environments (e.g. the Claude Code Stop-hook gate) silently prevent the
    spawned binary from writing its file, which would hard-fail these tests for
    reasons unrelated to the code under test. We probe with the SAME mechanism,
    in-context, and skip only when it genuinely cannot run — so CI and normal
    dev runs still exercise the real piping behavior AND still catch real
    regressions (a probe that works but a test that fails is a true failure).
    """
    import shutil
    import subprocess

    tee = shutil.which("tee")
    probe = tmp_path / ".pager_probe"
    ok = False
    if tee is not None:
        try:
            # Mirror the tests' own invocation exactly (inherit stdout/stderr,
            # which under pytest are the captured fds) so the probe sees the same
            # conditions — including a sandbox that blocks the spawned write.
            subprocess.run(  # noqa: S603 — fixed argv (resolved tee path)
                [tee, str(probe)],
                input="ok",
                text=True,
                check=False,
                timeout=10,
            )
            ok = probe.is_file() and probe.read_text(encoding="utf-8") == "ok"
        except (OSError, subprocess.SubprocessError):
            ok = False
    if not ok:
        pytest.skip(
            "environment cannot spawn a pager subprocess (sandboxed); the real "
            "piping behavior is exercised in CI and normal dev runs"
        )


@pytest.fixture
def emitted_auth(tmp_path: Path) -> Iterator[Path]:
    """Like `emitted`, but rendered WITH an auth component so the IR carries
    credential_fields (client_id/client_secret/scope/base_url). Importable as
    `fakesdk_cli` (env_prefix FAKESDK)."""
    ir = build_cli_ir(introspect("fakesdk", FIXTURE), _FAKESDK_CLI_CONFIG)[0]
    render_cli(
        ir,
        package="fakesdk_cli",
        out_dir=tmp_path,
        env_prefix="FAKESDK",
        auth=ScmOAuth(type="scm_oauth"),
    )
    sys.path.insert(0, str(tmp_path))
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    try:
        yield tmp_path
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
            del sys.modules[name]


def test_output_formats(emitted: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"id": "a1", "name": "slack", "nested": {"x": 1}}

    out.render(_Model(), fmt="json")
    assert '"name"' in capsys.readouterr().out  # json includes name

    out.render([_Model()], fmt="yaml")
    assert "name: slack" in capsys.readouterr().out

    out.render([_Model()], fmt="table")
    table = capsys.readouterr().out
    assert "id" in table and "name" in table and "a1" in table
    assert "nested" not in table  # dict columns are dropped from the table view


def _write_user_config(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def _write_user_env_file(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "environments.yml").write_text(body, encoding="utf-8")


def test_config_defaults_when_no_user_file(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    c = cfg.get()
    assert c.pager.enabled is False
    assert c.pager.command is None
    assert c.output.format == "json"
    assert cfg.load_config()[1] == ()  # no warnings
    assert cfg.load_config()[2] == ("packaged defaults",)
    assert cfg.default_output() == "json"


def test_config_packaged_defaults_match_models(emitted: Path) -> None:
    import yaml as _yaml

    cfg = importlib.import_module("fakesdk_cli._generated.config")
    data = _yaml.safe_load(cfg.packaged_default_text())
    assert cfg.ConfigFile.model_validate(data) == cfg.ConfigFile()


def test_config_homedir_override_and_env_precedence(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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


def test_config_unknown_key_warns_once(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pagre:\n    enabled: true\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.get()
    cfg.get()  # second call must not re-warn
    err = capsys.readouterr().err
    assert err.count("unknown config key 'configuration.pagre'") == 1


def test_config_wrong_type_falls_back(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  pager:\n    enabled: maybe\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False  # default applied
    err = capsys.readouterr().err
    assert "configuration.pager.enabled" in err and "default" in err


def test_config_malformed_yaml_ignores_file(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, ":: this is not yaml ::\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().output.format == "json"  # defaults survive
    assert "invalid YAML" in capsys.readouterr().err


def test_config_unreadable_file_warns_and_continues(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_config_bad_bool_env_ignored(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "banana")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.get().pager.enabled is False
    assert "not a boolean" in capsys.readouterr().err


def test_config_bad_bool_env_diagnostics(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FAKESDK_PAGER_ENABLED", "banana")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    cfg.get()
    err = capsys.readouterr().err
    assert "warning: " in err and "not a boolean" in err
    assert "✖" not in err


def _fake_client(recorder: list[Any]) -> tuple[Any, type]:
    """A stand-in matching the fixture facade shape; records calls into `recorder`."""
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(**kw: Any) -> dict[str, Any]:
                recorder.append((name, kw))
                return {"id": kw.get("id", "new")}

            return _call

    class _FakeClientCls:
        widgets = _Rec()
        gizmos = _Rec()
        things = _Rec()

        def paginate(self, method: Any, **kw: Any) -> Iterator[Any]:
            return iter(method(**kw) or [])

    return facade, _FakeClientCls


def test_runtime_create_vs_patch(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))

    rt.run(
        "create:widget",
        path={},
        body={"name": "foo", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    rt.run(
        "update:widget",
        path={"id": "w9"},
        body={"name": "bar"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls[0][0] == "create_widget"
    assert calls[1][0] == "patch_widget" and calls[1][1].get("id") == "w9"


def test_runtime_variant_wraps_body_and_fills_type(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.models as models

    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))

    rt.run(
        "create:gizmo:simple",
        path={},
        body={"name": "x"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    name, kw = calls[0]
    assert name == "create_gizmo"
    assert kw["type"] == "simple"  # H4: variant fills the path param
    wrapped = kw["create_gizmo_input"]
    assert isinstance(wrapped, models.CreateGizmoInput)  # H3: oneOf wrapper
    assert isinstance(wrapped.actual_instance, models.SimpleGizmoInput)
    assert wrapped.actual_instance.name == "x"


def test_runtime_dry_run_does_not_call(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "create:widget",
        path={},
        body={"name": "x", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=True,
        verbose=False,
    )
    assert calls == []
    assert "create:widget" in capsys.readouterr().out


def test_runtime_friendly_error_on_sdk_exception(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.exceptions as exc_mod
    import fakesdk.extras.facade as facade

    class _Boom:
        widgets = None

        def __init__(self) -> None:
            class _W:
                def create_widget(self, **kw: Any) -> Any:
                    raise exc_mod.OpenApiException("boom")

            self.widgets = _W()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Boom()))
    import pytest as _pytest

    with _pytest.raises(SystemExit) as ei:
        rt.run(
            "create:widget",
            path={},
            body={"name": "x", "priority": 1},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
    assert ei.value.code == 1
    assert "error:" in capsys.readouterr().err


def test_update_uses_patch(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # `update X --id` dispatches to the PATCH binding (PUT update_* is deferred).
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "update:widget",
        path={"id": "w1"},
        body={"name": "n"},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls[0][0] == "patch_widget"  # NOT update_widget (PUT deferred)


def test_create_without_id_creates(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "create:widget",
        path={},
        body={"name": "n", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls[0][0] == "create_widget"


def test_cli_runner_show_create_delete(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    calls: list[Any] = []
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


def test_cli_runner_variant_and_nonvariant_under_object(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade
    import fakesdk.models as models

    calls: list[Any] = []
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
    assert "create_gizmo" in names  # from `create gizmo simple`
    assert "patch_gizmo" in names  # from `update gizmo`
    create_call = next(kw for n, kw in calls if n == "create_gizmo")
    assert create_call["type"] == "simple"
    assert isinstance(create_call["create_gizmo_input"], models.CreateGizmoInput)


def test_runtime_coerces_int_query(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
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


def test_bool_body_flag_accepts_value_and_coerces(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A settable bool field takes a VALUE (--enabled true|false), like every other
    # field — NOT a Typer on/off flag. The string is coerced to a real bool before
    # the model is built. (Regression: native `bool` made Typer reject the value as
    # an unexpected extra argument.)
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    r = CliRunner()
    for raw, expected in [("true", True), ("false", False)]:
        calls.clear()
        res = r.invoke(
            main.app,
            [
                "create",
                "widget",
                "--name",
                "w",
                "--priority",
                "1",
                "--enabled",
                raw,
                "--output",
                "json",
            ],
        )
        assert res.exit_code == 0, res.output
        _, kw = next((n, k) for n, k in calls if n == "create_widget")
        body = kw["widget_input"]
        assert body.enabled is expected  # coerced str -> real bool


def test_bool_body_flag_rejects_non_bool_value(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unparseable bool errors cleanly (named flag, nonzero exit) — it must NOT be
    # silently coerced to False, nor escape as a raw traceback.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = _fake_client([])
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--enabled", "maybe"],
    )
    assert res.exit_code != 0
    # no traceback
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "enabled" in res.stderr


def test_invalid_json_flag_reports_clean_error(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Invalid JSON to a JSON-string flag (e.g. --spec / --urls) reports a clean,
    # flag-named error instead of dumping a raw JSONDecodeError traceback.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, fake_client_cls = _fake_client([])
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--spec", "notjson"],
    )
    assert res.exit_code != 0
    # no traceback
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "spec" in res.stderr


def test_cli_runner_request_actions(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    r = CliRunner()
    # request is a verb group
    assert "request" in r.invoke(main.app, ["--help"]).output
    res = r.invoke(
        main.app,
        [
            "request",
            "widget",
            "suspend",
            "--name",
            "W",
            "--priority",
            "1",
            "--output",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output
    res2 = r.invoke(
        main.app,
        [
            "request",
            "widget",
            "revoke",
            "--id",
            "W9",
            "--name",
            "X",
            "--priority",
            "1",
            "--output",
            "json",
        ],
    )
    assert res2.exit_code == 0, res2.output

    names = [c[0] for c in calls]
    assert "suspend_widget" in names
    assert "revoke_widget" in names
    revoke_call = next(kw for n, kw in calls if n == "revoke_widget")
    assert revoke_call.get("id") == "W9"


def test_output_defaults_to_json_not_table(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import contextlib
    import io

    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"id": "a1", "name": "slack"}

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out.render(_Model())  # no fmt → default
    text = buf.getvalue()
    assert '"id"' in text and '"name"' in text  # JSON, not a table or repr
    assert "_Model(" not in text  # no python repr


def test_to_data_never_leaks_repr(emitted: Path) -> None:
    import contextlib
    import io

    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Weird:  # no model_dump, not a scalar/dict/list
        def __repr__(self) -> str:
            return "<_Weird object at 0xdeadbeef>"

    data = out._to_data(_Weird())
    assert isinstance(data, str)  # converted, not passed through raw
    # render(json) must not crash and must not emit the angle-bracket repr as an object
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out.render(_Weird(), fmt="json")
    assert buf.getvalue().strip()  # produced some JSON string output


def test_cli_runner_show_defaults_to_json(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fakesdk.extras.facade as facade
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")

    calls: list[Any] = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )

    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])  # NO --output
    assert res.exit_code == 0, res.output
    assert '"id"' in res.output  # default JSON output
    assert "WidgetsApi" not in res.output and "object at 0x" not in res.output


def test_env_file_is_auto_loaded(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    # a .env in the CWD the user runs from
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / ".env").write_text("DEMO_TOKEN=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("DEMO_TOKEN", raising=False)

    seen: dict[str, Any] = {}

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(**kw: Any) -> list[Any]:
                return []

            return _call

    class _Client:
        widgets = _Rec()

        def paginate(self, m: Any, **kw: Any) -> Iterator[Any]:
            return iter([])

    def _from_env(cls: Any) -> _Client:
        import os

        # was .env loaded before from_env?
        seen["DEMO_TOKEN"] = os.environ.get("DEMO_TOKEN")
        return _Client()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(_from_env))

    res = CliRunner().invoke(main.app, ["show", "widget", "--output", "json"])
    assert res.exit_code == 0, res.output
    # _client() called load_dotenv() before from_env()
    assert seen["DEMO_TOKEN"] == "from-dotenv"


def test_create_missing_required_errors_cleanly(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["create", "widget"])  # missing required --name
    assert res.exit_code != 0 and (
        "Missing option" in res.output or "required" in res.output.lower()
    )


def test_update_requires_id(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["update", "widget", "--name", "x"])  # no --id
    assert res.exit_code != 0
    assert "--id" in res.output or "id" in res.output.lower()


def test_update_body_fields_optional(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app, ["update", "widget", "--id", "w1", "--output", "json"]
    )
    assert res.exit_code == 0, res.output  # no required body flags
    assert any(n == "patch_widget" for n, _ in calls)


def test_delete_requires_id(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(main.app, ["delete", "widget"])  # no --id
    assert res.exit_code != 0


def test_scalar_body_flags_use_real_types(emitted: Path, tmp_path: Path) -> None:
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
    assert ": int = typer.Option(" in code  # required int (create)
    assert "priority: int" in code  # priority typed as int
    # bool fields render value-style (str), NOT a native bool (which Typer would
    # turn into a valueless on/off flag); coerced to bool at runtime by _coerce.
    assert "enabled: str | None = typer.Option(None" in code


def test_scalar_type_validated_by_typer(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: object()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "abc"],
    )
    assert res.exit_code != 0  # 'abc' is not a valid int -> Typer rejects


def test_enum_flag_lists_choices_in_help(emitted: Path) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    h = CliRunner().invoke(main.app, ["create", "widget", "--help"]).output
    assert "values:" in h.lower()
    assert "red" in h.lower()  # a real Color choice (red/blue in the fixture)


def test_enum_flag_accepts_unlisted_value(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # permissive: SDK is LenientStrEnum -> unknown enum value ACCEPTED, not rejected
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = _fake_client(calls)
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: fake_client_cls())
    )
    res = CliRunner().invoke(
        main.app,
        [
            "create",
            "widget",
            "--name",
            "w",
            "--priority",
            "1",
            "--color",
            "chartreuse",
            "--output",
            "json",
        ],
    )
    assert res.exit_code == 0, res.output  # unlisted value passes through


_DEFAULT_FALLBACK = ["error", "message", "msg", "detail", "title", "description"]
_NESTED_ENV = {
    "wrappers": ["errorResponse", "error_response"],
    "error_field": "error",
    "errors_field": None,
    "message_field": "message",
    "code_field": "code",
    "fallback_keys": _DEFAULT_FALLBACK,
}
_LIST_ENV = {
    "wrappers": [],
    "error_field": None,
    "errors_field": "_errors",
    "message_field": "message",
    "code_field": "code",
    "fallback_keys": _DEFAULT_FALLBACK,
}


def test_error_headline_extraction(emitted: Path) -> None:
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")

    # --- the fakesdk CLI has NO error component, so only the generic, product-
    #     AGNOSTIC fallback vocabulary applies (the default _ERROR_ENVELOPE) ---
    assert d._error_headline({"message": "boom"}) == "boom"
    # RFC 7807: detail preferred over title
    assert (
        d._error_headline({"title": "Bad Request", "detail": "x out of range"})
        == "x out of range"
    )
    # gateway/transport `msg` lives in the generic tier
    assert d._error_headline({"msg": "Access denied"}) == "Access denied"
    assert d._error_headline({"error": "flat string"}) == "flat string"
    assert d._error_headline({"foo": 1}) is None
    assert d._error_headline("not a dict") is None
    # structured PRODUCT shapes are NOT recognized without a configured envelope
    assert d._error_headline({"_errors": [{"message": "x"}]}) is None
    assert d._error_headline({"errorResponse": {"error": "x"}}) is None

    # --- the generic template carries NO product-specific keys (the C2 guard) ---
    src = (emitted / "fakesdk_cli" / "_generated" / "diagnostics.py").read_text()
    assert "errorResponse" not in src
    assert '"_errors"' not in src

    # --- a NESTED envelope (config) drives wrapper-peel + nested-object extraction ---
    assert (
        d._error_headline(
            {
                "errorResponse": {
                    "error": "group name already exists",
                    "message": "failed to create device group",
                }
            },
            _NESTED_ENV,
        )
        == "group name already exists"  # `error` string preferred via fallback order
    )
    assert d._error_headline({"error": {"message": "nested"}}, _NESTED_ENV) == "nested"
    assert (
        d._error_headline({"error": {"code": "X", "message": "Y"}}, _NESTED_ENV)
        == "X: Y"
    )

    # --- a LIST envelope (config) drives _errors[] extraction ---
    assert (
        d._error_headline(
            {"_errors": [{"code": "API_I00035", "message": "Invalid Request Payload"}]},
            _LIST_ENV,
        )
        == "API_I00035: Invalid Request Payload"
    )
    assert (
        d._error_headline({"_errors": [{"message": "no code here"}]}, _LIST_ENV)
        == "no code here"
    )
    assert d._error_headline({"_errors": []}, _LIST_ENV) is None


def test_render_error_api_exception_to_stderr(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")

    class _Exc:  # duck-typed ApiException
        status = 400
        reason = "Bad Request"
        body = (
            '{"errorResponse":{"error":"group name already exists",'
            '"message":"failed to create device group"}}'
        )
        data = None

    d.render_error(_Exc())
    err = capsys.readouterr().err
    assert "400 Bad Request" in err
    assert "group name already exists" in err  # headline
    assert "errorResponse" in err and "failed to create device group" in err  # body
    assert "HTTPHeaderDict" not in err  # noise gone
    assert "response headers" not in err.lower()


def test_render_error_non_api(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    d.render_error(ValueError("bad --flag value"))
    err = capsys.readouterr().err
    assert "error: bad --flag value" in err


def test_cli_runner_api_error_is_pretty(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.exceptions
    import fakesdk.extras.facade as facade

    fexc: Any = fakesdk.exceptions

    class _Client:
        class widgets:  # noqa: N801
            @staticmethod
            def create_widget(**kw: Any) -> Any:
                raise fexc.ApiException(
                    status=400,
                    reason="Bad Request",
                    body='{"errorResponse":{"error":"widget name already exists",'
                    '"message":"failed to create widget"}}',
                )

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Client()))

    res = CliRunner().invoke(
        main.app, ["create", "widget", "--name", "dup", "--priority", "1"]
    )
    assert res.exit_code == 1, res.output
    assert "400 Bad Request" in res.output
    assert "widget name already exists" in res.output  # headline
    assert "errorResponse" in res.output  # full JSON body
    assert "HTTPHeaderDict" not in res.output
    assert "response headers" not in res.output.lower()


def test_render_error_non_json_body(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    for name in [n for n in sys.modules if n.startswith("fakesdk_cli")]:
        del sys.modules[name]
    d = importlib.import_module("fakesdk_cli._generated.diagnostics")

    class _Exc:
        status = 502
        reason = "Bad Gateway"
        body = "upstream timeout"
        data = None

    d.render_error(_Exc())
    err = capsys.readouterr().err
    assert "502 Bad Gateway" in err and "upstream timeout" in err


def test_render_none_is_silent(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A None result (e.g. delete / HTTP 204) prints nothing in any format."""
    out = importlib.import_module("fakesdk_cli._generated.output")
    for fmt in ("json", "yaml", "table"):
        out.render(None, fmt=fmt)
        captured = capsys.readouterr()
        assert captured.out == "", f"{fmt}: {captured.out!r}"
        assert captured.err == ""


def test_cli_runner_delete_silent_when_none(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A delete whose SDK method returns None succeeds with NO stdout (no 'null')."""
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            return lambda **kw: None  # SDK delete returns None (204)

    class _Client:
        def __getattr__(self, name: str) -> Any:
            return _Rec()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Client()))
    res = CliRunner().invoke(main.app, ["delete", "widget", "--id", "w1"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == ""  # no "null", no output on success


def test_show_flags_grouped_into_panels(emitted: Path, tmp_path: Path) -> None:
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
    m = re.search(r"def show_widget\(.*?\n\) ->", code, re.S)
    assert m is not None
    show_fn = m.group(0)
    assert 'rich_help_panel="Filters"' in show_fn  # --name (filter query param)
    assert 'rich_help_panel="Pagination"' in show_fn  # --limit + --all
    # --id (path) is NOT panelled; --output joined "Common" (2026-06-11)
    assert re.search(r'--id".*rich_help_panel', show_fn) is None
    assert re.search(r'--output", rich_help_panel="Common"', show_fn)


def test_show_help_renders_panels(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    out = CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    titles = _panel_titles(out)
    assert "Filters" in titles and "Pagination" in titles
    assert "Options" in titles  # default panel kept (domain flags + --help)


def test_render_dry_run_get_no_body(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render_dry_run("GET", "https://api.test/devices?limit=50", None)
    captured = capsys.readouterr().out
    assert "DRY RUN" in captured
    assert "GET" in captured and "https://api.test/devices?limit=50" in captured


def test_render_dry_run_post_with_body(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render_dry_run(
        "POST",
        "https://api.test/device-groups",
        {"name": "Kiosks", "platform": "Desktop Browser"},
    )
    captured = capsys.readouterr().out
    assert "POST" in captured and "device-groups" in captured
    assert '"name"' in captured and "Kiosks" in captured  # body JSON


def test_dry_run_falls_back_without_serialize(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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


def test_version_flag_wired(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    for n in [n for n in list(sys.modules) if n.startswith("fakesdk_cli")]:
        del sys.modules[n]
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--version"])
    assert res.exit_code == 0, res.output
    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    assert app_mod._DISTRIBUTION in res.output  # distribution name printed
    # not installed in the tmp render -> graceful "unknown", no crash
    assert app_mod._resolve_version() in res.output


def test_version_resolves_from_metadata(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    monkeypatch.setattr(app_mod._metadata, "version", lambda dist: "9.9.9")
    assert app_mod._resolve_version() == "9.9.9"


def _row(i: int) -> dict[str, Any]:
    return {
        "id": f"w{i}",
        "name": f"widget-{i}",
        "priority": i,
        "enabled": True,
        "tags": ["a", "b", "c", "d", "e"],
        "spec": {"x": 1},
        "members": [
            {"name": "alice"},
            {"name": "bob"},
            {"name": "carol"},
            {"name": "dave"},
        ],
    }


def test_table_unwraps_list_envelope_and_uses_default_columns(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    envelope = {"page_info": {"cursor": None}, "data": [_row(1), _row(2)]}
    out.render(
        envelope,
        fmt="table",
        default_columns=[("id", "id"), ("name", "name")],
        items_field="data",
    )
    text = capsys.readouterr().out
    assert "w1" in text and "widget-2" in text  # rows, not the envelope
    assert "page_info" not in text


def test_table_jmespath_columns_and_joined_preview(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    out.render(
        [_row(1)], fmt="table", columns=["name", "MEMBERS=members[].name", "tags"]
    )
    text = capsys.readouterr().out
    assert "MEMBERS" in text
    assert "alice, bob, carol, +1 more" in text  # list-of-dicts preview via path
    assert "a, b, c, +2 more" in text  # scalar list preview


def test_table_cell_rendering_rules(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    row: dict[str, Any] = {
        "id": "x",
        "gone": None,
        "flag": True,
        "nest": {"a": 1},
        "objs": [{"k": 1}, {"k": 2}],
    }
    out.render([row], fmt="table", columns=["id", "gone", "flag", "nest", "objs"])
    text = capsys.readouterr().out
    assert "true" in text  # bools lowercase
    assert '{"a":1}' in text  # dict -> compact json
    assert "2 items" in text  # dicts w/o name/id -> count


def test_table_heuristic_fallback_when_no_columns(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    rows = [
        {
            "created": "t",
            "name": "n1",
            "id": "i1",
            "deep": {"x": 1},
            "a": 1,
            "b": 2,
            "c": 3,
            "d": 4,
        }
    ]
    out.render(rows, fmt="table")  # no columns at all
    text = capsys.readouterr().out
    assert "id" in text and "name" in text  # preferred first
    assert "deep" not in text  # nested excluded
    # cap 6: id, name, created, a, b, c -> "d" doesn't fit
    assert " d " not in text


def test_columns_split_and_header_parsing(emitted: Path) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    specs = out.parse_columns(["id,OWNER=owner.name", "F=join(', ', tags)"])
    assert specs == [
        ("id", "id"),
        ("OWNER", "owner.name"),
        ("F", "join(', ', tags)"),
    ]  # comma inside () not split


def test_table_invalid_runtime_columns_exits_cleanly(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import pytest

    out = importlib.import_module("fakesdk_cli._generated.output")
    with pytest.raises(SystemExit):
        out.render([{"id": "x"}], fmt="table", columns=["bad[expr"])
    assert "invalid --columns" in capsys.readouterr().err


def test_columns_flag_implies_table_and_renders_curated(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(
        data=[
            models.Widget(id="w1", name="alpha", tags=["t1", "t2"]),
            models.Widget(id="w2", name="beta"),
        ]
    )

    class _W:
        def list_widgets(self, **kw: Any) -> Any:
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    runner = CliRunner()
    res = runner.invoke(
        app_mod.build_generated_app(), ["show", "widget", "--columns", "name,id"]
    )
    assert res.exit_code == 0, res.output
    assert "alpha" in res.output and "w2" in res.output
    assert "page_info" not in res.output  # envelope unwrapped
    assert "{" not in res.output  # table, not json


def test_show_without_columns_uses_ir_default_columns(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    models = importlib.import_module("fakesdk.models")

    page = models.WidgetList(data=[models.Widget(id="w1", name="alpha")])

    class _W:
        def list_widgets(self, **kw: Any) -> Any:
            return page

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    runner = CliRunner()
    res = runner.invoke(
        app_mod.build_generated_app(), ["show", "widget", "--output", "table"]
    )
    assert res.exit_code == 0, res.output
    # ir default columns put id/name first and exclude the nested spec field
    assert "id" in res.output and "name" in res.output
    assert "spec" not in res.output


def test_fakesdk_generated_lint_clean(tmp_path: Path) -> None:
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
        [
            ruff,
            "check",
            "--isolated",
            "--select",
            "E,F,I,UP,W",
            "--line-length",
            "88",
            str(gen),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_query_default_is_injected_and_overridable(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls: list[Any] = []

    class _W:
        def list_widgets(self, **kw: Any) -> list[Any]:
            calls.append(kw)
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    runner = CliRunner()

    # no flags -> cli.yml defaults flow into the SDK call (int correctly typed)
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}

    # user override wins
    res = runner.invoke(
        app_mod.build_generated_app(),
        ["show", "widget", "--name", "other", "--limit", "7"],
    )
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "other", "limit": 7}


def test_query_default_shown_in_help(emitted: Path) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    res = CliRunner().invoke(
        app_mod.build_generated_app(), ["show", "widget", "--help"]
    )
    assert res.exit_code == 0
    assert "default:" in res.output and "gadget" in res.output


def test_injected_defaults_not_sent_to_get_binding(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    app_mod = importlib.import_module("fakesdk_cli._generated.app")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    calls: list[Any] = []

    class _W:  # STRICT get signature, like the real SDK's @validate_call methods
        def get_widget_by_id(
            self, id: str, configuration_version: Any = None
        ) -> dict[str, Any]:
            calls.append({"id": id, "configuration_version": configuration_version})
            return {"id": id, "name": "x"}

        def list_widgets(self, **kw: Any) -> list[Any]:
            calls.append(kw)
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    runner = CliRunner()

    # get binding: the injected name/limit defaults must NOT reach the call
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"id": "w1", "configuration_version": None}

    # list binding still receives the defaults
    res = runner.invoke(app_mod.build_generated_app(), ["show", "widget"])
    assert res.exit_code == 0, res.output
    assert calls[-1] == {"name": "gadget", "limit": 50}


def test_model_body_defaults_still_not_rendered(emitted: Path) -> None:
    """CRITICAL INVARIANT: pydantic model defaults (Flag.default) must never
    become CLI flag defaults — PATCH would silently send them. WidgetInput.mode
    defaults to 'fast' in the model; the emitted option must stay None."""
    import pathlib

    src = (
        pathlib.Path(emitted) / "fakesdk_cli" / "_generated" / "commands" / "widgets.py"
    ).read_text(encoding="utf-8")
    mode_lines = [ln for ln in src.splitlines() if '"--mode"' in ln]
    assert mode_lines, "expected a --mode option in the emitted widgets module"
    for line in mode_lines:
        assert '"fast"' not in line  # model default must NOT be rendered
        assert "None" in line  # option default stays None


def test_output_default_comes_from_config(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: yaml\n")
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0
    assert "id: w1" in res.output  # yaml rendering proves the config default applied

    # and --help shows the effective default
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "yaml" in res.output


def test_pager_flag_present_and_run_wires_it(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    help_out = _strip_ansi(res.output)
    assert "--pager" in help_out and "--no-pager" in help_out

    out = importlib.import_module("fakesdk_cli._generated.output")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    seen: list[Any] = []

    from contextlib import contextmanager

    @contextmanager
    def _spy(flag: Any) -> Iterator[None]:
        seen.append(flag)
        yield

    monkeypatch.setattr(out, "maybe_paged", _spy)
    rt.run(
        "show:widget",
        path={"id": "w1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
        pager=True,
    )
    rt.run(
        "show:widget",
        path={"id": "w1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
        pager=False,
    )
    rt.run(
        "show:widget",
        path={"id": "w1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
        pager=None,
    )
    assert seen == [True, False, None]


def test_config_effective_dict_excludes_extras(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_config(
        home, "configuration:\n  output:\n    format: table\n    extra_key: 1\n"
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    eff = cfg.effective_dict()
    assert eff["configuration"]["output"] == {"format": "table"}


def test_yaml_output_has_no_trailing_blank_line(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"a": 1}

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert text.endswith("a: 1\n")
    assert not text.endswith("\n\n")


def test_yaml_output_colored_on_terminal(emitted: Path) -> None:
    import io

    from rich.console import Console

    out: Any = importlib.import_module("fakesdk_cli._generated.output")

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return {"name": "widget-1", "enabled": True}

    buf = io.StringIO()
    # force a TTY-like console; no_color=False ensures NO_COLOR env var is ignored
    out._console = Console(file=buf, force_terminal=True, no_color=False)
    out.render(_Model(), fmt="yaml")
    assert "\x1b[" in buf.getvalue()  # ANSI styling present on a terminal


def test_yaml_output_plain_and_round_trips_when_piped(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    out = importlib.import_module("fakesdk_cli._generated.output")
    payload = {"name": "widget-1", "enabled": True, "tags": ["a", "b"]}

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return payload

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert "\x1b[" not in text  # no ANSI off a terminal
    assert text.endswith("\n") and not text.endswith("\n\n")  # exactly one newline
    assert yaml.safe_load(text) == payload


def test_yaml_output_long_line_not_truncated_when_piped(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression guard: rich Syntax crops to width 80 off-TTY unless soft_wrap=True.
    import yaml

    out = importlib.import_module("fakesdk_cli._generated.output")
    payload = {"url": "https://example.com/" + "x" * 300}

    class _Model:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            return payload

    out.render(_Model(), fmt="yaml")
    text = capsys.readouterr().out
    assert yaml.safe_load(text) == payload  # full value, no truncation


def test_autopager_short_content_writes_direct(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "10")
    monkeypatch.setenv("COLUMNS", "80")
    pager = out._AutoPager("/definitely/not/a/pager")
    pager.show("one\ntwo\nthree\n")  # 3 lines < 10 -> no spawn attempt
    captured = capsys.readouterr()
    assert "one\ntwo\nthree\n" in captured.out
    assert captured.err == ""  # no missing-binary warning -> nothing was spawned


def test_autopager_tall_content_pipes_to_command(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pager_subprocess: None,
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    # Force a short console so 50 lines are unambiguously tall enough to page,
    # independent of the ambient terminal/env: Rich's size short-circuits when
    # both _width and _height are set (rich/console.py size property).
    monkeypatch.setattr(out._console, "_width", 80)
    monkeypatch.setattr(out._console, "_height", 5)
    sink = tmp_path / "paged.txt"
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager(f"tee {sink}").show(content)
    assert sink.read_text(encoding="utf-8") == content


def test_autopager_missing_binary_falls_back(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setattr(out._console, "_width", 80)
    monkeypatch.setattr(out._console, "_height", 5)

    # A missing pager binary surfaces as OSError from subprocess; inject it
    # deterministically rather than relying on the OS/sandbox to fail an exec,
    # which is what we're asserting the code tolerates.
    def _missing(*_a: object, **_k: object) -> None:
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(out.subprocess, "run", _missing)
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager("/definitely/not/a/pager").show(content)
    captured = capsys.readouterr()
    assert captured.out.endswith("line49\n")  # content not lost
    assert "pager command not found" in captured.err


def test_autopager_blank_command_falls_back(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setenv("LINES", "5")
    monkeypatch.setenv("COLUMNS", "80")
    content = "".join(f"line{i}\n" for i in range(50))
    out._AutoPager("   ").show(content)  # must not raise; content not lost
    assert capsys.readouterr().out.endswith("line49\n")


def test_pager_command_resolution(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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


def test_maybe_paged_skips_when_not_a_tty(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: False)
    with out.maybe_paged(True):
        out._console.print("hello")
    assert "hello" in capsys.readouterr().out  # rendered directly, no pager


def test_maybe_paged_uses_pager_when_tty(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    pager_subprocess: None,
) -> None:
    out = importlib.import_module("fakesdk_cli._generated.output")
    monkeypatch.setattr(out._console, "_width", 80)
    monkeypatch.setattr(out._console, "_height", 5)
    monkeypatch.setattr(out, "_stdout_is_tty", lambda: True)
    sink = tmp_path / "paged.txt"
    monkeypatch.setenv("PAGER", f"tee {sink}")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with out.maybe_paged(True):
        for i in range(50):
            out._console.print(f"row{i}")
    assert "row49" in sink.read_text(encoding="utf-8")


def test_config_show_yaml_routes_through_shared_console(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import io

    from rich.console import Console
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")

    # piped (non-TTY): plain YAML, no ANSI, content intact
    res = CliRunner().invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "\x1b[" not in res.output and "format: json" in res.output

    # forced terminal: config show YAML is colored via the shared _console
    out: Any = importlib.import_module("fakesdk_cli._generated.output")
    buf = io.StringIO()
    out._console = Console(file=buf, force_terminal=True, no_color=False)
    res2 = CliRunner().invoke(main.app, ["config", "show"])
    assert res2.exit_code == 0
    assert "\x1b[" in buf.getvalue()  # YAML went through print_yaml -> _console


def test_config_init_and_show_commands(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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
    assert res.exit_code == 2  # refuses without --force

    target.write_text("STALE SENTINEL\n", encoding="utf-8")
    res = r.invoke(main.app, ["config", "init", "--force"])
    assert res.exit_code == 0
    assert "STALE SENTINEL" not in target.read_text(encoding="utf-8")

    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "merged from" in res.output
    assert ".fakesdk_cli" in res.output  # homedir file listed as a source
    assert "format: json" in res.output


def test_config_group_in_its_own_help_panel(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--help"])
    assert res.exit_code == 0
    assert "config" in res.output
    # "CLI" must render as a dedicated panel TITLE (box header), not merely as a
    # word in help text — this fails if rich_help_panel="CLI" is dropped.
    assert any("CLI" in line and "─" in line for line in res.output.splitlines())


_PANEL_RE = re.compile(r"╭─+\s(.+?)\s─+╮")
# CI (e.g. GitHub Actions) renders the emitted CLI's Rich help in color, so the
# output carries ANSI escapes that split tokens and box borders; strip them before
# parsing so help-output assertions are deterministic across local and CI runs.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _panel_titles(help_output: str) -> list[str]:
    """Rich panel titles in render order from a --help screen."""
    titles: list[str] = []
    for line in _strip_ansi(help_output).splitlines():
        m = _PANEL_RE.search(line)
        if m:
            titles.append(m.group(1).strip())
    return titles


def test_common_options_panel_renders_last(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert res.exit_code == 0
    out = _strip_ansi(res.output)
    titles = _panel_titles(out)
    assert "Common" in titles
    assert titles[-1] == "Common"  # the lowest container
    # the five members appear after the Common header...
    idx = out.index("Common")
    tail = out[idx:]
    for flag in ("--output", "--columns", "--dry-run", "--verbose", "--pager"):
        assert flag in tail
    # ...and the domain flag stays in the default Options panel above it
    assert "--id" in out[:idx]
    # --help remains stock (default panel, i.e. before Common)
    assert "--help" in out[:idx]


def test_pagination_panel_precedes_common_on_non_list_commands(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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


def test_history_config_defaults_and_env(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    h = cfg.get().history
    assert h.enabled is True
    assert h.verbose is False
    assert h.file is None
    assert h.max_size_mb == 50
    assert cfg.effective_dict()["configuration"]["history"] == {
        "enabled": True,
        "verbose": False,
        "file": None,
        "max_size_mb": 50,
    }
    # env overrides (incl. int coercion through pydantic lax validation)
    monkeypatch.setenv("FAKESDK_HISTORY_ENABLED", "off")
    monkeypatch.setenv("FAKESDK_HISTORY_VERBOSE", "on")
    monkeypatch.setenv("FAKESDK_HISTORY_FILE", "/tmp/h.jsonl")  # noqa: S108
    monkeypatch.setenv("FAKESDK_HISTORY_MAX_SIZE_MB", "5")
    cfg.load_config.cache_clear()
    h = cfg.get().history
    assert h.enabled is False and h.verbose is True
    assert h.file == "/tmp/h.jsonl" and h.max_size_mb == 5  # noqa: S108


def test_logging_config_defaults_and_env(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    assert cfg.get().logging.level == "info"
    assert cfg.get().logging.file is None
    assert cfg.effective_dict()["configuration"]["logging"] == {
        "level": "info",
        "file": None,
    }
    # default path is under logs/ next to config.yml
    assert cfg.log_file_path().name == "fakesdk_cli.jsonl"
    assert cfg.log_file_path().parent.name == "logs"
    # env override
    monkeypatch.setenv("FAKESDK_LOGGING_LEVEL", "debug")
    cfg.load_config.cache_clear()
    assert cfg.get().logging.level == "debug"
    assert cfg.log_level_int("warn") == 30 and cfg.log_level_int("trace") == 5
    # FILE env override resolves through log_file_path()
    monkeypatch.setenv("FAKESDK_LOGGING_FILE", str(tmp_path / "custom.jsonl"))
    cfg.load_config.cache_clear()
    assert cfg.log_file_path() == tmp_path / "custom.jsonl"


def test_logging_invalid_level_warns_and_falls_back(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    (home / ".fakesdk_cli").mkdir(parents=True)
    (home / ".fakesdk_cli" / "config.yml").write_text(
        "configuration:\n  logging:\n    level: bogus\n", encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    # bad level is rejected by _validate's bounded retry -> falls back to default
    assert cfg.get().logging.level == "info"


def test_logging_captures_warnings_to_file_not_stderr(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json
    import logging
    import stat
    import warnings

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    ls = importlib.import_module("fakesdk_cli._generated.logging_setup")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    ls.init_logging()
    warnings.warn(
        "DemoEnum: value 'x' is not defined in the OpenAPI spec", stacklevel=1
    )
    for h in logging.getLogger("py.warnings").handlers:  # flush; do NOT shutdown
        h.flush()
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    assert log.exists()
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert stat.S_IMODE(log.parent.stat().st_mode) == 0o700
    line = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert line["level"] == "WARNING"
    assert "not defined in the OpenAPI spec" in line["msg"]
    # the JSONL record carries ts/logger fields
    assert line["ts"].endswith("Z") and line["logger"] == "py.warnings"
    # NOT on stderr
    assert "not defined in the OpenAPI spec" not in capsys.readouterr().err


def test_logging_does_not_touch_root_logger(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # M1: init_logging must NEVER mutate the root logger (that evicts pytest's
    # log-capture handler). Only the py.warnings + package loggers get the sink.
    import logging

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    root_before = list(logging.getLogger().handlers)
    ls = importlib.import_module("fakesdk_cli._generated.logging_setup")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    ls.init_logging()
    assert logging.getLogger().handlers == root_before  # root untouched
    assert len(logging.getLogger("py.warnings").handlers) == 1
    assert logging.getLogger("py.warnings").propagate is False
    assert logging.getLogger("fakesdk_cli").propagate is False


def test_logging_rotates_and_gzips(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import gzip
    import logging

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ls = importlib.import_module("fakesdk_cli._generated.logging_setup")
    log = tmp_path / "rot.jsonl"
    handler = ls._SecureRotatingFileHandler(
        str(log), maxBytes=80, backupCount=2, encoding="utf-8", delay=True
    )
    handler.setFormatter(ls._JsonlFormatter())
    handler.rotator = ls._gzip_rotator
    handler.namer = ls._gzip_namer
    rec_logger = logging.getLogger("fakesdk_cli._rot_test")
    rec_logger.handlers[:] = [handler]
    rec_logger.propagate = False
    rec_logger.setLevel(logging.INFO)
    try:
        rec_logger.info("first line that is reasonably long to force a rollover")
        rec_logger.info("second line that is also reasonably long for rollover")
        handler.flush()
        gz = tmp_path / "rot.jsonl.1.gz"
        assert gz.exists()
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            assert "first line" in f.read()
    finally:
        handler.close()
        rec_logger.handlers[:] = []


def test_config_set_unset(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import yaml as _yaml
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()
    cfg_file = home / ".fakesdk_cli" / "config.yml"

    # alias set -> nested logging.level
    assert r.invoke(main.app, ["config", "set", "loglevel", "debug"]).exit_code == 0
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert data["configuration"]["logging"]["level"] == "debug"

    # dotted set
    assert r.invoke(main.app, ["config", "set", "output.format", "yaml"]).exit_code == 0
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert data["configuration"]["output"]["format"] == "yaml"

    # bool coercion (history.enabled)
    assert (
        r.invoke(main.app, ["config", "set", "history.enabled", "false"]).exit_code == 0
    )
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert data["configuration"]["history"]["enabled"] is False

    # int coercion (history.max_size_mb)
    assert (
        r.invoke(main.app, ["config", "set", "history.max_size_mb", "7"]).exit_code == 0
    )
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert data["configuration"]["history"]["max_size_mb"] == 7

    # invalid value -> exit 2
    assert r.invoke(main.app, ["config", "set", "loglevel", "bogus"]).exit_code == 2
    # unknown key (resolved path unknown) -> exit 2
    assert r.invoke(main.app, ["config", "set", "nope.key", "x"]).exit_code == 2

    # unset reverts (via alias)
    assert r.invoke(main.app, ["config", "unset", "loglevel"]).exit_code == 0
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert "level" not in data.get("configuration", {}).get("logging", {})
    # unset of an unknown key -> exit 2 (validated against resolved path)
    assert r.invoke(main.app, ["config", "unset", "nope.key"]).exit_code == 2


def test_config_set_show_reflects(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()
    assert r.invoke(main.app, ["config", "set", "loglevel", "debug"]).exit_code == 0
    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "level: debug" in res.output


def test_app_inits_logging_and_mirrors_diag(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import json
    import logging

    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
    res = CliRunner().invoke(main.app, ["config", "show"])  # any command
    assert res.exit_code == 0, res.output
    diag = importlib.import_module("fakesdk_cli._generated.diagnostics")
    diag.warning("a mirrored diagnostic line")
    for h in logging.getLogger("fakesdk_cli").handlers:  # flush; never shutdown()
        h.flush()
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    assert log.exists()  # init ran at app build
    msgs = [
        json.loads(line)["msg"] for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert any("a mirrored diagnostic line" in m for m in msgs)  # diag -> log sink


def test_full_command_warning_not_on_stderr_but_in_log(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A Python warning raised during a real command run must land in the logfile
    # and NOT on the CLI's stderr.
    import json

    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()

    class _W:
        def list_widgets(self, **kw: Any) -> list[Any]:
            import warnings

            warnings.warn(
                "Color: value 'mauve' is not defined in the OpenAPI spec", stacklevel=1
            )
            return []

    class _Client:
        widgets = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    res = CliRunner().invoke(main.app, ["show", "widget", "--output", "json"])
    assert res.exit_code == 0, res.output
    assert "not defined in the OpenAPI spec" not in res.output
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    msgs = [
        json.loads(line)["msg"] for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert any("not defined in the OpenAPI spec" in m for m in msgs)


def test_dotenv_reaches_config_layer(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import os

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "FAKESDK_HISTORY_ENABLED=false\nFAKESDK_OUTPUT_FORMAT=yaml\n",
        encoding="utf-8",
    )
    try:
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        assert cfg.get().history.enabled is False  # .env -> config layer
        assert cfg.get().output.format == "yaml"
    finally:
        # load_dotenv writes into os.environ for the whole process — clean up
        os.environ.pop("FAKESDK_HISTORY_ENABLED", None)
        os.environ.pop("FAKESDK_OUTPUT_FORMAT", None)


def _hist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """Import the emitted history module against an isolated HOME."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return importlib.import_module("fakesdk_cli._generated.history")


def test_history_record_appends_with_incrementing_ids(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t1", "command": "show widget", "status": "success"})
    hist.record({"ts": "t2", "command": "create widget", "status": "error"})
    entries, corrupt = hist.read_entries(0)
    assert corrupt == 0
    assert [e["id"] for e in entries] == [1, 2]
    assert entries[0]["command"] == "show widget"
    path = hist.history_path()
    assert path.name == "history.jsonl" and path.parent.name == ".fakesdk_cli"


def test_history_disabled_writes_nothing(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    enabled: false\n")
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t", "command": "x", "status": "success"})
    assert not hist.history_path().exists()


def test_history_cap_warns_and_skips(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    max_size_mb: 0\n")
    hist = _hist(monkeypatch, tmp_path)
    p = hist.history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"id": 1, "command": "old", "status": "success"}\n', encoding="utf-8")
    hist.record({"ts": "t", "command": "new", "status": "success"})
    err = capsys.readouterr().err
    err_joined = err.replace("\n", " ")
    assert "not recorded" in err_joined
    assert "history.jsonl" in err_joined  # path referenced in warning
    assert "new" not in p.read_text(encoding="utf-8")  # nothing appended


def test_history_read_skips_corrupt_lines_and_limits(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hist = _hist(monkeypatch, tmp_path)
    p = hist.history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"id": 1, "command": "a", "status": "success"}\n'
        "NOT JSON AT ALL\n"
        '{"id": 2, "command": "b", "status": "success"}\n'
        '{"id": 3, "command": "c", "status": "error"}\n',
        encoding="utf-8",
    )
    entries, corrupt = hist.read_entries(0)
    assert corrupt == 1 and [e["id"] for e in entries] == [1, 2, 3]
    last_two, _ = hist.read_entries(2)
    assert [e["id"] for e in last_two] == [2, 3]
    assert hist.read_entry(2)["command"] == "b"
    assert hist.read_entry(99) is None
    # id assignment continues past a corrupt trailing line
    p.write_text(p.read_text(encoding="utf-8") + "garbage\n", encoding="utf-8")
    hist.record({"ts": "t", "command": "d", "status": "success"})
    assert hist.read_entry(4)["command"] == "d"


def test_history_write_failure_warns_and_continues(
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Scoped failure injection: a read-only parent dir (NOT a global Path.mkdir
    # patch — hist.Path IS pathlib.Path; patching the class mutates the world).
    import os as _os

    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    if _os.access(locked, _os.W_OK):  # running as root: permission bits ineffective
        pytest.skip("cannot make dir read-only (running as privileged user)")
    home = tmp_path / "home"
    _write_user_config(
        home, f"configuration:\n  history:\n    file: {locked / 'sub' / 'h.jsonl'}\n"
    )
    hist = _hist(monkeypatch, tmp_path)
    hist.record({"ts": "t", "command": "x", "status": "success"})  # must not raise
    assert "could not write history" in capsys.readouterr().err


def _run_show_widget(rt: Any, **over: Any) -> None:
    kw: dict[str, Any] = {
        "path": {"id": "w1"},
        "body": {},
        "query": {},
        "output": "json",
        "paginate_all": False,
        "dry_run": False,
        "verbose": False,
    }
    kw.update(over)
    rt.run("show:widget", **kw)


def test_runtime_records_success_and_error(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "show", "widget", "--id", "w1"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    _run_show_widget(rt)

    import fakesdk.exceptions

    fx: Any = fakesdk.exceptions

    def _boom(**kw: Any) -> Any:
        exc = fx.ApiException("nope")
        exc.status = 404
        exc.body = '{"message": "widget not found"}'
        raise exc

    class _Failing:
        widgets = type("W", (), {"get_widget_by_id": staticmethod(_boom)})()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Failing()))
    with pytest.raises(SystemExit):
        _run_show_widget(rt)

    entries, _ = hist.read_entries(0)
    assert len(entries) == 2
    ok, bad = entries
    assert ok["id"] == 1 and ok["status"] == "success"
    assert ok["command"] == "show widget --id w1"
    assert ok["sdk_method"] == "widgets.get_widget_by_id"
    assert "http_status" not in ok and isinstance(ok["duration_ms"], int)
    assert "request_body" not in ok  # verbose off by default
    assert bad["status"] == "error" and bad["http_status"] == 404
    assert "not found" in bad["error"]


def test_runtime_dry_run_leaves_no_trace(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    _run_show_widget(rt, dry_run=True)
    assert not hist.history_path().exists()


def test_meta_commands_leave_no_trace(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    assert CliRunner().invoke(main.app, ["config", "show"]).exit_code == 0
    assert not hist.history_path().exists()


def test_runtime_verbose_records_bodies(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    verbose: true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "create", "widget", "--name", "x"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "create:widget",
        path={},
        body={"name": "x", "priority": 1},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    (entry,), _ = hist.read_entries(0)
    assert entry["request_body"]["name"] == "x"
    assert entry["response_body"]["id"] == "new"


def test_show_cli_history_table_limit_entry(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    hist = importlib.import_module("fakesdk_cli._generated.history")
    for i in range(25):
        hist.record(
            {
                "ts": f"2026-06-12T0{i % 10}:00:00+00:00",
                "command": f"show widget --id w{i}",
                "status": "success",
            }
        )
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    res = r.invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "w24" in res.output  # newest included
    assert "w4" not in res.output  # default --limit 20 cuts the oldest 5
    assert "w5" in res.output

    res = r.invoke(main.app, ["show", "cli", "history", "--limit", "0"])
    assert "w0" in res.output  # everything

    res = r.invoke(main.app, ["show", "cli", "history", "--entry", "3"])
    assert res.exit_code == 0
    assert '"id"' in res.output and "w2" in res.output  # full JSON of entry 3

    res = r.invoke(main.app, ["show", "cli", "history", "--entry", "999"])
    assert res.exit_code == 2


def test_show_cli_history_empty_state(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "empty" in res.output


def test_runtime_verbose_paginate_all_records_list_body(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    verbose: true\n")
    monkeypatch.setenv("HOME", str(home))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "show:widget",
        path={},
        body={},
        query={},
        output="json",
        paginate_all=True,
        dry_run=False,
        verbose=False,
    )
    (entry,), _ = hist.read_entries(0)
    assert entry["status"] == "success"
    assert isinstance(entry["response_body"], list)


def _oag_fake_client(
    raise_exc: Exception | None = None, query: str = "?expand=1&tag=a&tag=b"
) -> tuple[Any, type]:
    """Fake with the openapi-generator shape: methods route via api_client.call_api."""
    import fakesdk.extras.facade as facade

    class _ApiClient:
        def call_api(
            self,
            method: str,
            url: str,
            header_params: Any = None,
            body: Any = None,
            post_params: Any = None,
            _request_timeout: Any = None,
        ) -> dict[str, Any]:
            if raise_exc is not None:
                raise raise_exc
            return {"id": "w1"}

    class _Widgets:
        def __init__(self) -> None:
            self.api_client = _ApiClient()

        def get_widget_by_id(self, **kw: Any) -> dict[str, Any]:
            return self.api_client.call_api(
                "GET", f"https://api.example.com/v1/widgets/{kw['id']}{query}"
            )

    class _Client:
        def __init__(self) -> None:
            self.widgets = _Widgets()

    return facade, _Client


def test_history_captures_http_method_and_uri(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    facade, client_cls = _oag_fake_client()
    client = client_cls()
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client))
    _run_show_widget(rt)
    (entry,), _ = hist.read_entries(0)
    assert entry["http_method"] == "GET"
    # the URI is logged WITHOUT the query string — params live in http_params only
    assert entry["http_uri"] == "https://api.example.com/v1/widgets/w1"
    assert entry["http_params"] == {"expand": "1", "tag": ["a", "b"]}
    # the call_api wrapper is restored after the call
    assert client.widgets.api_client.call_api.__name__ == "call_api"


def test_history_captures_http_fields_on_error(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import fakesdk.exceptions

    fx: Any = fakesdk.exceptions

    exc = fx.ApiException("boom")
    exc.status = 500
    exc.body = '{"message": "kaboom"}'
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    facade, client_cls = _oag_fake_client(raise_exc=exc, query="")
    monkeypatch.setattr(
        facade.Client, "from_env", classmethod(lambda cls: client_cls())
    )
    with pytest.raises(SystemExit):
        _run_show_widget(rt)
    (entry,), _ = hist.read_entries(0)
    assert entry["status"] == "error" and entry["http_status"] == 500
    assert entry["http_method"] == "GET"
    assert "widgets/w1" in entry["http_uri"]
    assert "http_params" not in entry  # no query string -> field omitted


def test_history_http_fields_absent_for_plain_fakes(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    _run_show_widget(rt)
    (entry,), _ = hist.read_entries(0)
    assert "http_method" not in entry and "http_uri" not in entry


def test_diagnostics_plain_format_no_color(emitted: Path) -> None:
    # Inject an explicit no_color StringIO console — the plain path needs no env/reload.
    d: Any = importlib.import_module("fakesdk_cli._generated.diagnostics")
    import io

    from rich.console import Console

    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, theme=d._THEME, no_color=True)
    d.set_min_level(d.Level.INFO)
    d.error("boom [x]")
    d.warning("careful")
    d.info("fyi")
    out = buf.getvalue()
    assert "error: boom [x]" in out  # bracket survives (markup off)
    assert "warning: careful" in out
    assert "info: fyi" in out
    assert "✖" not in out  # no icon when no-color


def test_diagnostics_styled_has_icon_on_terminal(emitted: Path) -> None:
    d: Any = importlib.import_module("fakesdk_cli._generated.diagnostics")
    import io

    from rich.console import Console

    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, theme=d._THEME, force_terminal=True)
    d.set_min_level(d.Level.INFO)
    d.error("boom")
    assert "✖" in buf.getvalue()  # icon present on a terminal


def test_diagnostics_min_level_suppresses(emitted: Path) -> None:
    d: Any = importlib.import_module("fakesdk_cli._generated.diagnostics")
    import io

    from rich.console import Console

    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, no_color=True)
    d.set_min_level(d.Level.ERROR)  # quiet
    d.warning("hidden")
    d.info("hidden")
    d.error("shown")
    out = buf.getvalue()
    assert "shown" in out and "hidden" not in out
    d.set_min_level(d.Level.INFO)  # reset for other tests


def test_render_error_http_via_diagnostics(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    d: Any = importlib.import_module("fakesdk_cli._generated.diagnostics")
    import io

    from rich.console import Console

    buf = io.StringIO()
    d._err_console = Console(stderr=True, file=buf, no_color=True)

    class _Exc:  # duck-typed ApiException (matches the other render_error tests)
        status = 404
        reason = "Not Found"
        body = '{"error": {"message": "nope"}}'

    d.render_error(_Exc())
    out = buf.getvalue()
    assert "error: 404 Not Found — nope" in out
    assert "nope" in out


def test_bool_error_uses_diagnostics_format(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--enabled", "maybe"],
    )
    assert res.exit_code == 2
    assert res.exception is None or isinstance(res.exception, SystemExit)
    assert "error: --enabled: invalid boolean" in res.stderr
    assert "got: 'maybe'" in res.stderr


def test_invalid_json_flag_enriched(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--spec", "notjson"],
    )
    assert res.exit_code == 2
    assert "error: --spec: invalid JSON" in res.stderr
    assert "expected: a JSON object" in res.stderr  # spec is a dict field
    assert "got: 'notjson'" in res.stderr


def test_quiet_flag_sets_diagnostics_min_level(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # -q wires through run() to diagnostics.set_min_level(ERROR); absent -> INFO.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    calls: list[Any] = []
    monkeypatch.setattr(d, "set_min_level", lambda lvl: calls.append(lvl))
    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    r = CliRunner()
    r.invoke(main.app, ["create", "widget", "--name", "w", "--priority", "1", "-q"])
    assert d.Level.ERROR in calls
    calls.clear()
    r.invoke(main.app, ["create", "widget", "--name", "w", "--priority", "1"])
    assert d.Level.INFO in calls


def test_quiet_keeps_errors(emitted: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Errors are never suppressed by -q.
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = _fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    res = CliRunner().invoke(
        main.app,
        [
            "create",
            "widget",
            "--name",
            "w",
            "--priority",
            "1",
            "--enabled",
            "maybe",
            "-q",
        ],
    )
    assert res.exit_code == 2
    assert "error: --enabled" in res.stderr


# --- PR3: named environments ---------------------------------------------------


def test_env_resolve_environment_expands_refs(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod:\n"
        "    client_id: abc123\n"
        "    client_secret: ${PROD_SECRET}\n"
        "    scope: tsg_id:1234\n"
        "    base_url: https://api.example.com\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROD_SECRET", "s3cr3t")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert cfg.default_environment() == "prod"
    resolved = cfg.resolve_environment("prod")
    assert resolved == {
        "client_id": "abc123",
        "client_secret": "s3cr3t",  # ${PROD_SECRET} expanded from the process env
        "scope": "tsg_id:1234",
        "base_url": "https://api.example.com",
    }
    # an unset ${VAR} resolves to None, not the literal
    monkeypatch.delenv("PROD_SECRET", raising=False)
    assert cfg.resolve_environment("prod")["client_secret"] is None


def test_config_yml_stray_environments_key_is_flagged(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Environments live in environments.yml now. A stray `environments:` in
    # config.yml is genuinely misplaced, so load_config flags it as an unknown
    # key rather than silently swallowing it — this guards the decoupling.
    home = tmp_path / "home"
    _write_user_config(
        home,
        "configuration:\n  output:\n    format: json\n"
        "environments:\n  prod:\n    client_id: x\n",
    )
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    warnings = cfg.load_config()[1]
    assert any("environments" in w for w in warnings), warnings


def _capture_facade_kwargs(rt: Any, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Monkeypatch the thin _facade_from_env seam to capture threaded kwargs."""
    captured: dict[str, Any] = {}

    def _fake(**kw: Any) -> Any:
        captured.update(kw)
        return object()

    monkeypatch.setattr(rt, "_facade_from_env", _fake)
    return captured


def test_env_vars_override_active_environment(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod:\n"
        "    client_id: ENVID\n"
        "    client_secret: ${PROD_SECRET}\n"
        "    scope: prod-scope\n"
        "    base_url: https://api.example.com\n",
    )
    monkeypatch.setenv("HOME", str(home))
    # chdir off the source tree so find_dotenv(usecwd=True) can't discover a
    # developer .env above the repo and pollute the credential env vars.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PROD_SECRET", "envfile-secret")
    monkeypatch.setenv("CLIENT_ID", "SHELLID")  # exported -> beats the config value
    monkeypatch.delenv("CLIENT_SECRET", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("SCOPE", raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    captured = _capture_facade_kwargs(rt, monkeypatch)
    rt._client()
    assert captured["client_id"] == "SHELLID"  # env var wins
    assert captured["client_secret"] == "envfile-secret"  # from the env file
    assert captured["host"] == "https://api.example.com"  # base_url -> host kwarg
    assert captured["scope"] == "prod-scope"  # resolved from the env file


def test_env_empty_exported_var_still_wins(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Presence-not-truthiness precedence: an exported-but-empty var still beats
    # the config value. Demonstrated on the OPTIONAL base_url field (an empty
    # REQUIRED field is now rejected by the pre-flight — see
    # test_empty_exported_required_var_is_treated_as_missing). The required
    # fields are fully supplied so the pre-flight passes.
    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod:\n"
        "    client_id: ENVID\n"
        "    client_secret: ENVSECRET\n"
        "    scope: ENVSCOPE\n"
        "    base_url: https://config-host\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # isolate from any developer .env above the repo
    monkeypatch.setenv("BASE_URL", "")  # exported but empty -> presence wins
    monkeypatch.delenv("CLIENT_ID", raising=False)
    monkeypatch.delenv("CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SCOPE", raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    captured = _capture_facade_kwargs(rt, monkeypatch)
    rt._client()
    assert captured["host"] == ""  # empty string threaded, NOT "https://config-host"
    assert captured["client_id"] == "ENVID"  # required fields still resolve


def test_generated_cli_imports_only_declared_dependencies(emitted_auth: Path) -> None:
    # Regression guard: the generated CLI must import only its DECLARED deps.
    # `typer>=0.12` resolves to the slim core, which does NOT install top-level
    # `click` — so emitting `import click` (or any other undeclared package)
    # breaks every generated CLI at import time. Scan every emitted module.
    import ast

    allowed = set(sys.stdlib_module_names) | {
        # third-party deps declared in scaffold_context._CLI_DEPS
        "typer",
        "rich",
        "yaml",
        "dotenv",
        "jmespath",
        "pydantic",
        "pygments",
        # the emitted CLI package itself + the SDK it wraps
        "fakesdk_cli",
        "fakesdk",
    }
    offenders: dict[str, set[str]] = {}
    for py in (emitted_auth / "fakesdk_cli" / "_generated").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                tops = {node.module.split(".")[0]}
            else:
                continue
            for top in tops - allowed:
                offenders.setdefault(py.name, set()).add(top)
    assert not offenders, f"generated CLI imports undeclared dependencies: {offenders}"


def test_env_unknown_selected_environment_errors(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A selected-but-undefined environment must fail loudly, not silently fall
    # back to ambient env-var auth (which could use unintended credentials).
    home = tmp_path / "home"
    _write_user_env_file(home, "default_environment: ghost\nenvironments: {}\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as exc:
        rt._client()
    assert exc.value.code == 2


def test_env_selection_precedence(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod: {client_id: PROD}\n"
        "  staging: {client_id: STAGING}\n"
        # adhoc is the env actually threaded by _client below, so it carries the
        # full required credential set; prod/staging only exercise name resolution.
        "  adhoc: {client_id: ADHOC, client_secret: SEC, scope: SC}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # isolate from any developer .env above the repo
    # ensure no per-field env vars interfere with the field assertions
    for var in ("CLIENT_ID", "CLIENT_SECRET", "BASE_URL", "SCOPE"):
        monkeypatch.delenv(var, raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    # default_environment alone
    monkeypatch.delenv("FAKESDK_ENVIRONMENT", raising=False)
    rt.select_environment(None)
    assert rt._selected_environment() == "prod"

    # {PREFIX}_ENVIRONMENT beats default_environment
    monkeypatch.setenv("FAKESDK_ENVIRONMENT", "staging")
    assert rt._selected_environment() == "staging"

    # the -e contextvar beats both
    rt.select_environment("adhoc")
    assert rt._selected_environment() == "adhoc"

    # and the selected env's fields are what _client threads
    captured = _capture_facade_kwargs(rt, monkeypatch)
    rt._client()
    assert captured["client_id"] == "ADHOC"
    rt.select_environment(None)  # reset module contextvar for other tests


def test_env_option_in_help_and_threads_selection(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "environments:\n"
        "  staging: {client_id: STAGING, client_secret: SEC, scope: SC}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # isolate from any developer .env above the repo
    for var in (
        "CLIENT_ID",
        "CLIENT_SECRET",
        "BASE_URL",
        "SCOPE",
        "FAKESDK_ENVIRONMENT",
    ):
        monkeypatch.delenv(var, raising=False)

    main = importlib.import_module("fakesdk_cli.main")
    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    help_out = _strip_ansi(
        CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    )
    assert "--environment" in help_out
    # the short flag is advertised alongside the long flag
    env_line = next(ln for ln in help_out.splitlines() if "--environment" in ln)
    assert "-e" in env_line

    captured: dict[str, Any] = {}

    class _W:
        def list_widgets(self, **kw: Any) -> list[Any]:
            return []

    class _Client:
        widgets = _W()

        def paginate(self, m: Any, **kw: Any) -> Iterator[Any]:
            return iter([])

    def _fake(**kw: Any) -> Any:
        captured.update(kw)
        return _Client()

    monkeypatch.setattr(rt, "_facade_from_env", _fake)
    res = CliRunner().invoke(
        main.app, ["show", "widget", "-e", "staging", "--output", "json"]
    )
    assert res.exit_code == 0, res.output
    assert captured["client_id"] == "STAGING"  # -e selected staging's fields


# --- bugfix: clean missing-credentials error (descriptor-driven pre-flight) ---


def test_missing_credentials_message_guides_user(
    emitted_auth: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Nothing configured at all (no environment, no credential env vars): the
    # first command must fail cleanly (exit 2, no raw traceback) and guide the
    # user toward BOTH remediation paths.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)  # isolate from any developer .env above the repo
    for var in (
        "CLIENT_ID",
        "CLIENT_SECRET",
        "SCOPE",
        "BASE_URL",
        "FAKESDK_ENVIRONMENT",
    ):
        monkeypatch.delenv(var, raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as ei:
        rt._client()
    assert ei.value.code == 2

    err = _strip_ansi(capsys.readouterr().err)
    assert "no credentials configured" in err
    assert "environment create" in err  # primary remediation path
    # names the three genuinely-required vars; base_url (host has a default) is NOT
    assert "CLIENT_ID" in err and "CLIENT_SECRET" in err and "SCOPE" in err
    assert "BASE_URL" not in err


def test_missing_credentials_names_active_environment(
    emitted_auth: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # An environment is active (default_environment) but incomplete: the message
    # names the environment and only the fields it is still missing.
    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\nenvironments:\n  prod: {client_id: PRODID}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    for var in (
        "CLIENT_ID",
        "CLIENT_SECRET",
        "SCOPE",
        "BASE_URL",
        "FAKESDK_ENVIRONMENT",
    ):
        monkeypatch.delenv(var, raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as ei:
        rt._client()
    assert ei.value.code == 2

    err = _strip_ansi(capsys.readouterr().err)
    assert "environment 'prod'" in err
    assert "CLIENT_SECRET" in err and "SCOPE" in err
    assert "CLIENT_ID" not in err  # client_id IS set -> not listed as missing


def test_missing_credentials_via_dash_e_selected_environment(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The -e contextvar path (distinct from default_environment) is covered too.
    home = tmp_path / "home"
    _write_user_env_file(home, "environments:\n  staging: {client_id: STAGINGID}\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    for var in (
        "CLIENT_ID",
        "CLIENT_SECRET",
        "SCOPE",
        "BASE_URL",
        "FAKESDK_ENVIRONMENT",
    ):
        monkeypatch.delenv(var, raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    rt.select_environment("staging")
    try:
        with pytest.raises(SystemExit) as ei:
            rt._client()
        assert ei.value.code == 2
    finally:
        rt.select_environment(None)  # reset module contextvar for other tests


def test_empty_exported_required_var_is_treated_as_missing(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # An exported-but-EMPTY required var is unusable (the SDK rejects it with
    # `if not v`); the pre-flight mirrors that and fails cleanly rather than
    # threading "" and letting a raw RuntimeError escape.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLIENT_ID", "")  # exported but empty
    monkeypatch.setenv("CLIENT_SECRET", "s")
    monkeypatch.setenv("SCOPE", "sc")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("FAKESDK_ENVIRONMENT", raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as ei:
        rt._client()
    assert ei.value.code == 2


def test_auth_failure_renders_clean_error(
    emitted_auth: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Credentials ARE present but the auth/token request still fails: this must
    # be a clean error (exit 1, no traceback), distinct from misconfiguration.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLIENT_ID", "id")
    monkeypatch.setenv("CLIENT_SECRET", "secret")
    monkeypatch.setenv("SCOPE", "scope")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("FAKESDK_ENVIRONMENT", raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    def _boom(**kw: Any) -> Any:
        raise RuntimeError("token endpoint returned 503")

    monkeypatch.setattr(rt, "_facade_from_env", _boom)
    with pytest.raises(SystemExit) as ei:
        rt._client()
    assert ei.value.code == 1

    err = _strip_ansi(capsys.readouterr().err)
    assert "authentication failed" in err
    assert "token endpoint returned 503" in err


def test_auth_failure_reraises_under_verbose(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # With --verbose the original traceback is preserved for debugging.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLIENT_ID", "id")
    monkeypatch.setenv("CLIENT_SECRET", "secret")
    monkeypatch.setenv("SCOPE", "scope")
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("FAKESDK_ENVIRONMENT", raising=False)

    rt = importlib.import_module("fakesdk_cli._generated.runtime")

    def _boom(**kw: Any) -> Any:
        raise RuntimeError("token endpoint returned 503")

    monkeypatch.setattr(rt, "_facade_from_env", _boom)
    with pytest.raises(RuntimeError, match="token endpoint returned 503"):
        rt._client(verbose=True)


def test_no_auth_runtime_has_no_credential_preflight(emitted: Path) -> None:
    # The pre-flight is gated on ir.credential_fields: a no-auth CLI must not
    # emit any of the credential-error machinery.
    src = (emitted / "fakesdk_cli" / "_generated" / "runtime.py").read_text(
        encoding="utf-8"
    )
    assert "no credentials configured" not in src
    assert "authentication failed" not in src


# --- PR3: gating (no-auth CLI must be unaffected) -----------------------------


def test_no_auth_client_calls_facade_with_no_args(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    captured: dict[str, Any] = {"called": False, "kwargs": None}

    def _fake(**kw: Any) -> Any:
        captured["called"] = True
        captured["kwargs"] = kw
        return object()

    monkeypatch.setattr(rt, "_facade_from_env", _fake)
    rt._client()
    assert captured["called"] is True
    assert captured["kwargs"] == {}  # no credential threading for a no-auth CLI


def test_no_auth_help_has_no_environment_flag(emitted: Path) -> None:
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    help_out = _strip_ansi(
        CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    )
    assert "--environment" not in help_out
    # a no-auth CLI also has no environment helpers / contextvar on the runtime
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    assert not hasattr(rt, "select_environment")
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    assert not hasattr(cfg, "resolve_environment")


# --- PR4: top-level `environment` command group -------------------------------


def _read_config_yml(home: Path) -> dict[str, Any]:
    import yaml as _yaml

    text = (home / ".fakesdk_cli" / "config.yml").read_text(encoding="utf-8")
    data: dict[str, Any] = _yaml.safe_load(text)
    return data


def _read_environments_yml(home: Path) -> dict[str, Any]:
    import yaml as _yaml

    text = (home / ".fakesdk_cli" / "environments.yml").read_text(encoding="utf-8")
    data: dict[str, Any] = _yaml.safe_load(text)
    return data


def test_env_create_writes_fields_and_auto_activates(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")

    # secret supplied via the hidden prompt; the rest on the command line
    res = CliRunner().invoke(
        main.app,
        [
            "environment",
            "create",
            "prod",
            "--client-id",
            "abc",
            "--scope",
            "tsg_id:1",
            "--base-url",
            "https://api",
        ],
        input="s3cr3t\n",
    )
    assert res.exit_code == 0, res.output
    assert "s3cr3t" not in res.output  # hidden prompt must not echo the secret

    data = _read_environments_yml(home)
    assert data["environments"]["prod"] == {
        "client_id": "abc",
        "client_secret": "s3cr3t",  # captured from the hidden prompt, stored as-is
        "scope": "tsg_id:1",
        "base_url": "https://api",
    }
    # the environments file must be private (it holds client_secret)
    import stat

    mode = stat.S_IMODE((home / ".fakesdk_cli" / "environments.yml").stat().st_mode)
    assert mode == 0o600, oct(mode)
    # no default existed -> the first environment is auto-activated
    assert data["default_environment"] == "prod"


def test_env_create_stores_ref_verbatim(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")

    res = CliRunner().invoke(
        main.app,
        [
            "environment",
            "create",
            "prod",
            "--client-id",
            "abc",
            "--client-secret",
            "${PROD_SECRET}",  # a ${VAR} reference, not a literal
            "--scope",
            "s",
            "--base-url",
            "u",
        ],
    )
    assert res.exit_code == 0, res.output
    data = _read_environments_yml(home)
    # stored VERBATIM — NOT resolved at write time
    assert data["environments"]["prod"]["client_secret"] == "${PROD_SECRET}"


def test_env_create_duplicate_requires_force(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    args = [
        "environment",
        "create",
        "prod",
        "--client-id",
        "abc",
        "--client-secret",
        "s",
        "--scope",
        "s",
        "--base-url",
        "u",
    ]
    assert r.invoke(main.app, args).exit_code == 0
    # re-create the same name -> refused with exit code 2
    res_dup = r.invoke(main.app, args)
    assert res_dup.exit_code == 2, res_dup.output
    assert "already exists" in (res_dup.stderr or res_dup.output)
    # --force overwrites
    res_force = r.invoke(
        main.app,
        [
            "environment",
            "create",
            "prod",
            "--force",
            "--client-id",
            "xyz",
            "--client-secret",
            "s",
            "--scope",
            "s",
            "--base-url",
            "u",
        ],
    )
    assert res_force.exit_code == 0, res_force.output
    assert _read_environments_yml(home)["environments"]["prod"]["client_id"] == "xyz"


def test_env_activate_undefined_errors_and_existing_updates_default(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod: {client_id: PROD}\n"
        "  staging: {client_id: STAGING}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()

    # activating an undefined environment -> exit code 2
    res_bad = r.invoke(main.app, ["environment", "activate", "nope"])
    assert res_bad.exit_code == 2, res_bad.output
    assert "no such environment" in (res_bad.stderr or res_bad.output)
    # the default is unchanged after the failed activate
    assert _read_environments_yml(home)["default_environment"] == "prod"

    # activating an existing one updates default_environment
    res_ok = r.invoke(main.app, ["environment", "activate", "staging"])
    assert res_ok.exit_code == 0, res_ok.output
    assert _read_environments_yml(home)["default_environment"] == "staging"


def test_env_show_marks_active_and_hides_secrets(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: staging\n"
        "environments:\n"
        "  prod: {client_id: PROD, client_secret: prodsecret}\n"
        "  staging: {client_id: STAGING, client_secret: stagesecret}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "show"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert "prod" in out and "staging" in out
    # the active environment is marked
    active_line = next(ln for ln in out.splitlines() if ln.startswith("staging"))
    assert "active" in active_line
    prod_line = next(ln for ln in out.splitlines() if ln.startswith("prod"))
    assert "active" not in prod_line
    # NEVER print field values / secrets
    assert "prodsecret" not in out and "stagesecret" not in out
    assert "PROD" not in out and "STAGING" not in out


def test_env_show_empty_says_so(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "show"])
    assert res.exit_code == 0, res.output
    assert "no environments" in (res.output + (res.stderr or "")).lower()


def test_env_show_no_active_after_force_delete(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    # environments present but NO default_environment (reachable via
    # `delete --force` of the active env while others remain)
    _write_user_env_file(home, "environments:\n  staging: {client_id: STAGING}\n")
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "show"])
    assert res.exit_code == 0, res.output
    out = (res.output + (res.stderr or "")).lower()
    assert "staging" in out
    assert "no active environment" in out  # auth falls back to env vars
    assert "(active)" not in res.output  # nothing is marked active


def test_env_delete_non_default_removes_it(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\n"
        "environments:\n"
        "  prod: {client_id: PROD}\n"
        "  staging: {client_id: STAGING}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "delete", "staging"])
    assert res.exit_code == 0, res.output
    data = _read_environments_yml(home)
    assert "staging" not in data["environments"]
    assert "prod" in data["environments"]
    assert data["default_environment"] == "prod"


def test_env_delete_default_without_force_errors(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\nenvironments:\n  prod: {client_id: PROD}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "delete", "prod"])
    assert res.exit_code == 2
    msg = res.stderr or res.output
    assert "active environment" in msg
    # environment must NOT have been removed
    data = _read_environments_yml(home)
    assert "prod" in data["environments"]


def test_env_delete_force_removes_default_and_unsets_key(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_env_file(
        home,
        "default_environment: prod\nenvironments:\n  prod: {client_id: PROD}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "delete", "--force", "prod"])
    assert res.exit_code == 0, res.output
    data = _read_environments_yml(home)
    assert "prod" not in data.get("environments", {})
    assert "default_environment" not in data


def test_env_delete_unknown_name_errors(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "delete", "ghost"])
    assert res.exit_code == 2
    assert "no such environment" in (res.stderr or res.output)


def test_env_create_preserves_existing_environments(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    # config.yml holds only configuration (unrelated to environment writes)
    _write_user_config(home, "configuration:\n  output:\n    format: table\n")
    # environments.yml holds the existing environments
    _write_user_env_file(
        home,
        "default_environment: existing\nenvironments:\n  existing: {client_id: OLD}\n",
    )
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(
        main.app,
        [
            "environment",
            "create",
            "prod",
            "--client-id",
            "abc",
            "--client-secret",
            "s",
            "--scope",
            "s",
            "--base-url",
            "u",
        ],
    )
    assert res.exit_code == 0, res.output
    env_data = _read_environments_yml(home)
    # prior environment survives in environments.yml
    assert env_data["environments"]["existing"] == {"client_id": "OLD"}
    assert "prod" in env_data["environments"]
    # a default already existed -> NOT overwritten by the new env
    assert env_data["default_environment"] == "existing"
    # config.yml remains unchanged
    cfg_data = _read_config_yml(home)
    assert cfg_data["configuration"]["output"]["format"] == "table"


def test_env_create_secret_never_written_to_history(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Secret-leak guard: a config-group command records NO history, so a secret
    (whether on the command line or prompted) never lands in the history file."""
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")

    # secret on the command line
    res = CliRunner().invoke(
        main.app,
        [
            "environment",
            "create",
            "prod",
            "--client-id",
            "abc",
            "--client-secret",
            "s3cr3t",
            "--scope",
            "s",
            "--base-url",
            "u",
        ],
    )
    assert res.exit_code == 0, res.output
    history = home / ".fakesdk_cli" / "history.jsonl"
    # config-group commands do not go through runtime.run() -> no history at all
    assert not history.exists()


def test_env_group_emitted_and_visible_in_help(
    emitted_auth: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # the hand-written module is emitted verbatim for an auth CLI
    assert (
        emitted_auth / "fakesdk_cli" / "_generated" / "environment_commands.py"
    ).exists()
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()
    top_help = _strip_ansi(r.invoke(main.app, ["--help"]).output)
    assert "environment" in top_help  # top-level group, in the "CLI" panel
    env_help = _strip_ansi(r.invoke(main.app, ["environment", "--help"]).output)
    for verb in ("create", "activate", "show", "delete"):
        assert verb in env_help
    # the dynamic per-field create options are present, by kebab name
    create_help = _strip_ansi(
        r.invoke(main.app, ["environment", "create", "--help"]).output
    )
    assert "--client-id" in create_help
    assert "--client-secret" in create_help
    assert "--scope" in create_help
    assert "--base-url" in create_help


def test_no_auth_has_no_environment_group(
    emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # the hand-written module is NOT emitted for a no-auth CLI
    assert not (
        emitted / "fakesdk_cli" / "_generated" / "environment_commands.py"
    ).exists()
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()
    top_help = _strip_ansi(r.invoke(main.app, ["--help"]).output)
    assert "environment" not in top_help
    # the absent top-level group fails to invoke
    res = r.invoke(main.app, ["environment", "--help"])
    assert res.exit_code != 0


# --- bugfix: clear error for get-by-id-only show commands (no list op) --------


def test_show_id_only_reports_no_list_operation(
    emitted: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A show command backed only by get-by-id (no list) reports a clear
    'no list operation' error with an --id hint, not the generic no-match.
    Fails at _pick_binding before any client is constructed -> no fake facade."""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    with pytest.raises(SystemExit) as exc:
        rt.run(
            "show:thing",
            path={},
            body={},
            query={},
            output="json",
            paginate_all=False,
            dry_run=False,
            verbose=False,
        )
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "has no list operation" in err
    assert "--id" in err


def test_show_id_only_with_id_still_dispatches_get(
    emitted: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Positive control: the get-by-id path is unaffected — `show thing --id t1`
    still dispatches get_thing(thing_id="t1")."""
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    calls: list[Any] = []
    facade, fake_cls = _fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    rt.run(
        "show:thing",
        path={"thing_id": "t1"},
        body={},
        query={},
        output="json",
        paginate_all=False,
        dry_run=False,
        verbose=False,
    )
    assert calls and calls[0][0] == "get_thing"
    assert calls[0][1].get("thing_id") == "t1"
