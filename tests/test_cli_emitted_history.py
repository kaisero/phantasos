import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


def _write_user_config(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def test_history_config_defaults_and_env(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_history_disabled_writes_nothing(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    _write_user_config(home, f"configuration:\n  history:\n    file: {locked / 'sub' / 'h.jsonl'}\n")
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
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "show", "widget", "--id", "w1"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
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
        widget = type("W", (), {"get": staticmethod(_boom)})()

    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: _Failing()))
    with pytest.raises(SystemExit):
        _run_show_widget(rt)

    entries, _ = hist.read_entries(0)
    assert len(entries) == 2
    ok, bad = entries
    assert ok["id"] == 1 and ok["status"] == "success"
    assert ok["command"] == "show widget --id w1"
    assert ok["sdk_method"] == "widget.get"  # <object>.<clean verb>
    assert "http_status" not in ok and isinstance(ok["duration_ms"], int)
    assert "request_body" not in ok  # verbose off by default
    assert bad["status"] == "error" and bad["http_status"] == 404
    assert "not found" in bad["error"]


def test_runtime_dry_run_leaves_no_trace(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    _run_show_widget(rt, dry_run=True)
    assert not hist.history_path().exists()


def test_meta_commands_leave_no_trace(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    assert CliRunner().invoke(main.app, ["config", "show"]).exit_code == 0
    assert not hist.history_path().exists()


def test_runtime_verbose_records_bodies(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    verbose: true\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(sys, "argv", ["fakesdk-cli", "create", "widget", "--name", "x"])
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
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


def test_show_cli_history_table_limit_entry(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_show_cli_history_empty_state(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["show", "cli", "history"])
    assert res.exit_code == 0
    assert "empty" in res.output


def test_runtime_verbose_paginate_all_records_list_body(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  history:\n    verbose: true\n")
    monkeypatch.setenv("HOME", str(home))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
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


def _oag_fake_client(raise_exc: Exception | None = None, query: str = "?expand=1&tag=a&tag=b") -> tuple[Any, type]:
    """Fake with the openapi-generator + facade shape: the api_client lives on the
    CLIENT (facade level), shared by every wrapper, and the typed `widget` wrapper
    routes its `get` through `client.api_client.call_api`. The runtime now wraps
    the facade-level call_api, so the capture sees the request."""
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

    class _Widget:
        def __init__(self, api_client: Any) -> None:
            self._api_client = api_client

        def get(self, **kw: Any) -> Any:
            return self._api_client.call_api("GET", f"https://api.example.com/v1/widgets/{kw['id']}{query}")

    class _Client:
        def __init__(self) -> None:
            self.api_client = _ApiClient()
            self.widget = _Widget(self.api_client)

    return facade, _Client


def test_history_captures_http_method_and_uri(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    # the call_api wrapper is restored after the call (wrapped at the facade level)
    assert client.api_client.call_api.__name__ == "call_api"


def test_history_captures_http_fields_on_error(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import fakesdk.exceptions

    fx: Any = fakesdk.exceptions

    exc = fx.ApiException("boom")
    exc.status = 500
    exc.body = '{"message": "kaboom"}'
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    facade, client_cls = _oag_fake_client(raise_exc=exc, query="")
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: client_cls()))
    with pytest.raises(SystemExit):
        _run_show_widget(rt)
    (entry,), _ = hist.read_entries(0)
    assert entry["status"] == "error" and entry["http_status"] == 500
    assert entry["http_method"] == "GET"
    assert "widgets/w1" in entry["http_uri"]
    assert "http_params" not in entry  # no query string -> field omitted


def test_history_http_fields_absent_for_plain_fakes(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rt = importlib.import_module("fakesdk_cli._generated.runtime")
    hist = importlib.import_module("fakesdk_cli._generated.history")
    calls: list[Any] = []
    facade, fake_cls = fake_client(calls)
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda cls: fake_cls()))
    _run_show_widget(rt)
    (entry,), _ = hist.read_entries(0)
    assert "http_method" not in entry and "http_uri" not in entry
