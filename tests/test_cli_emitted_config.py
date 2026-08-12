import importlib
from pathlib import Path
from typing import Any

import pytest


def _write_user_config(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def test_config_defaults_when_no_user_file(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_config_effective_dict_excludes_extras(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    _write_user_config(home, "configuration:\n  output:\n    format: table\n    extra_key: 1\n")
    monkeypatch.setenv("HOME", str(home))
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    eff = cfg.effective_dict()
    assert eff["configuration"]["output"] == {"format": "table"}


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


def test_config_init_and_show_commands(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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


def test_config_group_in_its_own_help_panel(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["--help"])
    assert res.exit_code == 0
    assert "config" in res.output
    # "CLI" must render as a dedicated panel TITLE (box header), not merely as a
    # word in help text — this fails if rich_help_panel="CLI" is dropped.
    assert any("CLI" in line and "─" in line for line in res.output.splitlines())


def test_config_set_unset(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    assert r.invoke(main.app, ["config", "set", "history.enabled", "false"]).exit_code == 0
    data = _yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    assert data["configuration"]["history"]["enabled"] is False

    # int coercion (history.max_size_mb)
    assert r.invoke(main.app, ["config", "set", "history.max_size_mb", "7"]).exit_code == 0
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


def test_config_set_show_reflects(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    r = CliRunner()
    assert r.invoke(main.app, ["config", "set", "loglevel", "debug"]).exit_code == 0
    res = r.invoke(main.app, ["config", "show"])
    assert res.exit_code == 0
    assert "level: debug" in res.output


def test_dotenv_reaches_config_layer(emitted: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
