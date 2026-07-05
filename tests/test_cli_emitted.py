import importlib
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

# Single source in conftest (functions that need CliConfig import it locally).
from conftest import _FAKESDK_CLI_CONFIG, FIXTURE
from phantasos.generator.cli.classify import build_cli_ir, cli_operations
from phantasos.generator.cli.render_cli import render_cli


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


def test_scalar_body_flags_use_real_types(emitted: Path, tmp_path: Path) -> None:
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import CliConfig
    from phantasos.generator.cli.render_cli import render_cli

    inv = cli_operations("fakesdk", FIXTURE)
    # intentionally exercises the un-deepened (models=None) path: this asserts only
    # on scalar body-flag typing (name/priority/enabled), not skeletons/model_ref.
    ir, _ = build_cli_ir(inv, CliConfig())
    render_cli(ir, package="fakesdk_cli", out_dir=tmp_path)
    code = (
        tmp_path / "fakesdk_cli" / "_generated" / "commands" / "widget.py"
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
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # permissive: SDK is LenientStrEnum -> unknown enum value ACCEPTED, not rejected
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _, fake_client_cls = fake_client(calls)
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
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with render_and_import(emitted, "fakesdk_cli"):  # fresh import; purges on exit
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
    emitted: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with render_and_import(emitted, "fakesdk_cli"):  # fresh import; purges on exit
        from typer.testing import CliRunner

        main = importlib.import_module("fakesdk_cli.main")
        import fakesdk.exceptions
        import fakesdk.extras.facade as facade

        fexc: Any = fakesdk.exceptions

        class _Client:
            class widget:  # noqa: N801  (object wrapper attr)
                @staticmethod
                def create(**kw: Any) -> Any:
                    raise fexc.ApiException(
                        status=400,
                        reason="Bad Request",
                        body='{"errorResponse":{"error":"widget name already exists",'
                        '"message":"failed to create widget"}}',
                    )

        monkeypatch.setattr(
            facade.Client, "from_env", classmethod(lambda cls: _Client())
        )

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
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with render_and_import(emitted, "fakesdk_cli"):  # fresh import; purges on exit
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


def test_show_help_renders_panels(
    emitted: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Keep NO_COLOR (not TERM=dumb): a dumb terminal drops the box borders that
    # _panel_titles/_panel_section rely on.
    monkeypatch.setenv("NO_COLOR", "1")
    from typer.testing import CliRunner

    with render_and_import(emitted, "fakesdk_cli"):  # fresh import; purges on exit
        main = importlib.import_module("fakesdk_cli.main")
        out = CliRunner().invoke(main.app, ["show", "widget", "--help"]).output
    titles = _panel_titles(out)
    assert "Filters" in titles and "Pagination" in titles  # was source rich_help_panel
    assert "Options" in titles  # default panel kept (domain flags + --help)
    # membership — behavioral, strictly subsumes the deleted source-regex asserts:
    assert "--name" in _panel_section(out, "Filters")
    assert "--limit" in _panel_section(out, "Pagination")
    assert "--all" in _panel_section(out, "Pagination")
    assert "--id" in _panel_section(out, "Options")  # --id NOT panelled -> default
    # ...and specifically NOT a filter:
    assert "--id" not in _panel_section(out, "Filters")
    # source fact #4 (--output joins Common), now self-contained:
    assert "--output" in _panel_section(out, "Common")


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
    # _dry_run tries fakesdk.api_client (absent) -> falls back to call-ref string
    # naming the wrapper dispatch target (`<object>.<verb>`).
    res = CliRunner().invoke(
        main.app,
        ["create", "widget", "--name", "w", "--priority", "1", "--dry-run"],
    )
    assert res.exit_code == 0, res.output
    assert "DRY-RUN create:widget" in res.output and "widget.create" in res.output


def test_version_flag_wired(
    emitted: Path,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    with render_and_import(emitted, "fakesdk_cli"):  # fresh import; purges on exit
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
        def list(self, *, all_pages: bool = False, **kw: Any) -> Any:
            return page

    class _Client:
        widget = _W()

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
        def list(self, *, all_pages: bool = False, **kw: Any) -> Any:
            return page

    class _Client:
        widget = _W()

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
    from phantasos.generator.cli.modelschema import build_model_registry

    inv = cli_operations("fakesdk", FIXTURE)
    ir = build_cli_ir(
        inv, _FAKESDK_CLI_CONFIG, models=build_model_registry("fakesdk", FIXTURE, inv)
    )[0]
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
        def list(self, *, all_pages: bool = False, **kw: Any) -> list[Any]:
            calls.append(kw)
            return []

    class _Client:
        widget = _W()

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


def test_model_body_defaults_still_not_rendered(emitted: Path) -> None:
    """CRITICAL INVARIANT: pydantic model defaults (Flag.default) must never
    become CLI flag defaults — PATCH would silently send them. WidgetInput.mode
    defaults to 'fast' in the model; the emitted option must stay None."""
    import pathlib

    src = (
        pathlib.Path(emitted) / "fakesdk_cli" / "_generated" / "commands" / "widget.py"
    ).read_text(encoding="utf-8")
    mode_lines = [ln for ln in src.splitlines() if '"--mode"' in ln]
    assert mode_lines, "expected a --mode option in the emitted widgets module"
    for line in mode_lines:
        assert '"fast"' not in line  # model default must NOT be rendered
        assert "None" in line  # option default stays None


def test_output_default_comes_from_config(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: yaml\n")
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    calls: list[Any] = []
    _facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    res = CliRunner().invoke(main.app, ["show", "widget", "--id", "w1"])
    assert res.exit_code == 0
    assert "id: w1" in res.output  # yaml rendering proves the config default applied

    # and --help shows the effective default
    res = CliRunner().invoke(main.app, ["show", "widget", "--help"])
    assert "yaml" in res.output


def test_pager_flag_present_and_run_wires_it(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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
    _facade, fake_cls = fake_client(calls)
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


_PANEL_RE = re.compile(r"╭─+\s(.+?)\s─+╮")

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


def _panel_section(help_output: str, title: str) -> str:
    """ANSI-stripped text of the Rich panel named `title`: from its header line to
    the next panel header (exclusive), or to EOF for the last panel."""
    lines = _strip_ansi(help_output).splitlines()
    starts = [
        (i, m.group(1).strip())
        for i, line in enumerate(lines)
        if (m := _PANEL_RE.search(line))
    ]
    for idx, (i, name) in enumerate(starts):
        if name == title:
            end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
            return "\n".join(lines[i:end])
    return ""


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


def test_emitted_help_shows_json_skeleton(emitted: Path) -> None:
    import os
    import subprocess

    # Force a wide, non-interactive terminal so Rich does NOT wrap the help columns
    # (a wrapped "[json: WidgetProfile]" would split the token and flake the assert).
    env = {**os.environ, "COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}
    # The emitted package's entry point lives in ``main.py`` (hand-owned); there
    # is no ``__main__.py``, so ``-m fakesdk_cli`` would not be runnable — target
    # ``fakesdk_cli.main`` (the same module the console-script wires up).
    out = subprocess.run(
        [sys.executable, "-m", "fakesdk_cli.main", "create", "widget", "--help"],
        capture_output=True,
        text=True,
        cwd=str(emitted),
        env=env,
    )
    text = out.stdout + out.stderr
    # Assert ONLY the two short, wrap-safe tokens here; the exact compact-JSON
    # skeleton string is asserted in the _flag_view unit test (no wrapping there).
    assert "[json:" in text and "WidgetProfile" in text
