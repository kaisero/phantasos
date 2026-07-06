import importlib
import logging
import re
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _write_user_config(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yml").write_text(body, encoding="utf-8")


def _write_user_env_file(home: Path, body: str) -> None:
    d = home / ".fakesdk_cli"
    d.mkdir(parents=True, exist_ok=True)
    (d / "environments.yml").write_text(body, encoding="utf-8")


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
            def _call(*, all_pages: bool = False, **kw: Any) -> list[Any]:
                return []

            return _call

    class _Client:
        widget = _Rec()

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


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


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
        def list(self, *, all_pages: bool = False, **kw: Any) -> list[Any]:
            return []

    class _Client:
        widget = _W()

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


# `default_after` sentinels: the written env file's `default_environment` key must
# be ABSENT after the delete, or assertion on it is skipped entirely.
_DEFAULT_UNSET = object()
_DEFAULT_SKIP = object()


@pytest.mark.parametrize(
    (
        "env_yaml",
        "args",
        "exit_code",
        "err_substr",
        "present",
        "absent",
        "default_after",
    ),
    [
        # non-default removed: file present, others + default survive
        pytest.param(
            "default_environment: prod\n"
            "environments:\n"
            "  prod: {client_id: PROD}\n"
            "  staging: {client_id: STAGING}\n",
            ["staging"],
            0,
            None,
            ["prod"],
            ["staging"],
            "prod",
            id="non_default_removes_it",
        ),
        # deleting the active env without --force errors; nothing removed
        pytest.param(
            "default_environment: prod\nenvironments:\n  prod: {client_id: PROD}\n",
            ["prod"],
            2,
            "active environment",
            ["prod"],
            [],
            _DEFAULT_SKIP,
            id="default_without_force_errors",
        ),
        # --force removes the active env AND unsets the default_environment key
        pytest.param(
            "default_environment: prod\nenvironments:\n  prod: {client_id: PROD}\n",
            ["--force", "prod"],
            0,
            None,
            [],
            ["prod"],
            _DEFAULT_UNSET,
            id="force_removes_default_and_unsets_key",
        ),
        # unknown name errors (no env file written at all)
        pytest.param(
            None,
            ["ghost"],
            2,
            "no such environment",
            [],
            [],
            _DEFAULT_SKIP,
            id="unknown_name_errors",
        ),
    ],
)
def test_env_delete(
    env_yaml: str | None,
    args: list[str],
    exit_code: int,
    err_substr: str | None,
    present: list[str],
    absent: list[str],
    default_after: object,
    emitted_auth: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    home = tmp_path / "home"
    if env_yaml is not None:
        _write_user_env_file(home, env_yaml)
    monkeypatch.setenv("HOME", str(home))
    main = importlib.import_module("fakesdk_cli.main")
    res = CliRunner().invoke(main.app, ["environment", "delete", *args])
    assert res.exit_code == exit_code, res.output
    if err_substr is not None:
        assert err_substr in (res.stderr or res.output)
    if env_yaml is not None:
        data = _read_environments_yml(home)
        envs = data.get("environments", {})
        for name in present:
            assert name in envs
        for name in absent:
            assert name not in envs
        if default_after is _DEFAULT_UNSET:
            assert "default_environment" not in data
        elif default_after is not _DEFAULT_SKIP:
            assert data["default_environment"] == default_after


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


def test_env_fields_carry_env_var_and_client_kwarg(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        assert cfg._ENV_FIELDS, "auth build must have credential fields"
        f = cfg._ENV_FIELDS[0]
        assert set(f) >= {"name", "secret", "env_var", "client_kwarg"}
        assert isinstance(f["env_var"], str) and f["env_var"]
        assert isinstance(f["client_kwarg"], str) and f["client_kwarg"]


def _cfg(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> ModuleType:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    ctx = render_and_import(out, "fakesdk_cli")
    ctx.__enter__()
    cfg = importlib.import_module("fakesdk_cli._generated.config")
    cfg.load_config.cache_clear()
    return cfg


def test_resolve_effective_env_overrides_stored(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    # write a named environment with a stored client_id
    envs = {
        "environments": {"prod": {"client_id": "stored-id"}},
        "default_environment": "prod",
    }
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    # exported CLIENT_ID overrides the stored value (presence semantics)
    eff = {
        f.name: f for f in cfg.resolve_effective("prod", env={"CLIENT_ID": "env-id"})
    }
    assert eff["client_id"].value == "env-id"
    assert eff["client_id"].source == cfg._Source.ENV
    assert eff["client_id"].env_var == "CLIENT_ID"
    # a stored-only field reports STORED
    eff2 = {f.name: f for f in cfg.resolve_effective("prod", env={})}
    assert eff2["client_id"].value == "stored-id"
    assert eff2["client_id"].source == cfg._Source.STORED


def test_resolve_effective_empty_credential_env_wins_presence(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    envs = {"environments": {"prod": {"client_id": "stored-id"}}}
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    # exported-but-EMPTY CLIENT_ID wins for credentials (presence, not truthiness)
    eff = {f.name: f for f in cfg.resolve_effective("prod", env={"CLIENT_ID": ""})}
    assert eff["client_id"].value == "" and eff["client_id"].source == cfg._Source.ENV


def test_resolve_effective_stored_ref_expands(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    envs = {"environments": {"prod": {"client_id": "${MY_ID}"}}}
    cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
    cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
    monkeypatch.setenv("MY_ID", "from-ref")
    # Isolate from a developer .env that an earlier test's load_config() may have
    # injected into os.environ — a real exported CLIENT_ID would win by presence
    # semantics and mask the stored ${MY_ID} we are exercising here.
    for var in ("CLIENT_ID", "CLIENT_SECRET", "SCOPE", "BASE_URL"):
        monkeypatch.delenv(var, raising=False)
    eff = {
        f.name: f
        for f in cfg.resolve_effective("prod", env=dict(__import__("os").environ))
    }
    assert eff["client_id"].value == "from-ref"
    assert eff["client_id"].source == cfg._Source.STORED_REF


def test_resolve_effective_unset(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg = _cfg(emit_cli, render_and_import, monkeypatch, tmp_path)
    eff = {f.name: f for f in cfg.resolve_effective(None, env={})}
    assert (
        eff["client_id"].value is None and eff["client_id"].source == cfg._Source.UNSET
    )


def test_client_credentials_parity(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {"environments": {"prod": {"client_id": "stored", "scope": "s"}}}
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        # replicate the OLD _client credential resolution; compare to the resolver
        env = {"CLIENT_ID": "envid"}
        old = {}
        legacy_env = cfg.resolve_environment("prod")
        for f in cfg._ENV_FIELDS:
            ev = env.get(f["env_var"])
            val = ev if ev is not None else legacy_env.get(f["name"])
            if val is not None:
                old[f["client_kwarg"]] = val
        new = {}
        for e in cfg.resolve_effective("prod", env=env):
            if e.kind == "credential" and e.value is not None:
                new[e.client_kwarg] = e.value
        assert new == old  # identical overrides dict -> identical client behavior


def test_selected_environment_source(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli._generated.runtime")
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        cfg.load_config.cache_clear()
        envs = {
            "environments": {"prod": {}, "staging": {}},
            "default_environment": "prod",
        }
        cfg.environments_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.environments_path().write_text(__import__("yaml").safe_dump(envs))
        assert rt._selected_environment_source() == ("prod", "default")
        monkeypatch.setenv("FAKESDK_ENVIRONMENT", "staging")
        # A prior test may have run the CLI's logging_setup.init(), which sets
        # propagate=False on the "fakesdk_cli" logger; that would stop _ENV_LOG's
        # record from reaching caplog's root handler. Restore propagation here
        # (monkeypatch reverts it at teardown).
        monkeypatch.setattr(logging.getLogger("fakesdk_cli"), "propagate", True)
        with caplog.at_level(logging.DEBUG, logger="fakesdk_cli.env"):
            assert rt._selected_environment_source() == ("staging", "env")
            assert rt._selected_environment() == "staging"  # [0] parity
        assert any("staging" in r.message for r in caplog.records)
        monkeypatch.setenv("FAKESDK_ENVIRONMENT", "")  # empty -> falls through
        assert rt._selected_environment_source() == ("prod", "default")
