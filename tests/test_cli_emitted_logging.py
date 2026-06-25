import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


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
        def list(self, *, all_pages: bool = False, **kw: Any) -> list[Any]:
            import warnings

            warnings.warn(
                "Color: value 'mauve' is not defined in the OpenAPI spec", stacklevel=1
            )
            return []

    class _Client:
        widget = _W()

    monkeypatch.setattr(rt, "_client", lambda **kw: _Client())
    res = CliRunner().invoke(main.app, ["show", "widget", "--output", "json"])
    assert res.exit_code == 0, res.output
    assert "not defined in the OpenAPI spec" not in res.output
    log = home / ".fakesdk_cli" / "logs" / "fakesdk_cli.jsonl"
    msgs = [
        json.loads(line)["msg"] for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert any("not defined in the OpenAPI spec" in m for m in msgs)


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
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = fake_client([])
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
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = fake_client([])
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
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # -q wires through run() to diagnostics.set_min_level(ERROR); absent -> INFO.
    from typer.testing import CliRunner

    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    d = importlib.import_module("fakesdk_cli._generated.diagnostics")
    calls: list[Any] = []
    monkeypatch.setattr(d, "set_min_level", lambda lvl: calls.append(lvl))
    _, cls = fake_client([])
    monkeypatch.setattr(facade.Client, "from_env", classmethod(lambda c: cls()))
    r = CliRunner()
    r.invoke(main.app, ["create", "widget", "--name", "w", "--priority", "1", "-q"])
    assert d.Level.ERROR in calls
    calls.clear()
    r.invoke(main.app, ["create", "widget", "--name", "w", "--priority", "1"])
    assert d.Level.INFO in calls


def test_quiet_keeps_errors(
    fake_client: Callable[[list[Any]], tuple[Any, type]],
    emitted: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Errors are never suppressed by -q.
    from typer.testing import CliRunner

    monkeypatch.setenv("NO_COLOR", "1")
    main = importlib.import_module("fakesdk_cli.main")
    import fakesdk.extras.facade as facade

    _, cls = fake_client([])
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
