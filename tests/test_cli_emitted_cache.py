"""Auth token cache — emitted through the fakesdk CLI (rendered WITH auth)."""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def test_cache_config_defaults_and_env(
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
        assert cfg.get().cache.enabled is True
        assert cfg.get().cache.dir is None
        assert cfg.cache_dir_path() == tmp_path / ".fakesdk" / "cache"
        # env override (presence-based, bool coercion)
        monkeypatch.setenv("FAKESDK_CACHE_ENABLED", "false")
        cfg.load_config.cache_clear()
        assert cfg.get().cache.enabled is False
        # effective_dict (drives `config show`) includes the cache section
        monkeypatch.delenv("FAKESDK_CACHE_ENABLED", raising=False)
        cfg.load_config.cache_clear()
        assert cfg.effective_dict()["configuration"]["cache"] == {
            "enabled": True,
            "dir": None,
        }


def test_cache_packaged_defaults_match_models(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Defaults-sync for the AUTH-gated cache section (the repo's own
    test_config_packaged_defaults_match_models uses the NON-auth fixture, so the
    `cache:` block is invisible to it — enforce parity here)."""
    import yaml as _yaml

    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        cfg = importlib.import_module("fakesdk_cli._generated.config")
        data = _yaml.safe_load(cfg.packaged_default_text())
        assert cfg.ConfigFile.model_validate(data) == cfg.ConfigFile()
        assert data["configuration"]["cache"] == {"enabled": True, "dir": None}


def test_cache_store_roundtrip_perms_and_isolation(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module(
            "fakesdk_cli._generated.config"
        ).load_config.cache_clear()
        k1 = ac._key("https://auth/", "id-A", "scope-1")
        k2 = ac._key("https://auth/", "id-B", "scope-1")  # different principal
        assert k1 != k2 and len(k1) == 12
        assert ac.read(k1) is None  # miss
        ac.write(k1, "tok-A", 9999999999.0)
        assert ac.read(k1) == ("tok-A", 9999999999.0)  # hit
        # secret/token never leak into the key; file is 0600, dir 0700
        f = ac.cache_dir() / f"token-{k1}.json"
        assert oct(f.stat().st_mode & 0o777) == "0o600"
        assert oct(ac.cache_dir().stat().st_mode & 0o777) == "0o700"
        assert "tok-A" not in f.name and "id-A" not in f.name
        # list + clear
        ac.write(k2, "tok-B", 8888888888.0)
        assert sorted(ac.list_entries()) == sorted(
            [(k1, 9999999999.0), (k2, 8888888888.0)]
        )
        assert ac.clear() == 2 and ac.read(k1) is None


def test_cache_read_tolerates_corruption(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module(
            "fakesdk_cli._generated.config"
        ).load_config.cache_clear()
        k = ac._key("u", "c", "s")
        (ac.cache_dir() / f"token-{k}.json").write_text("{not json")
        assert ac.read(k) is None  # corrupt -> miss (fail open), no raise


class _StubTM:
    """Mimics the SDK TokenManager's fields the cache couples to."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at = 0.0
        self._token_url = "https://auth.example/token"
        self._client_id = "cid"
        self._scope = "scope-x"
        self.fetches = 0

    def token(self) -> str:
        if self._token is None or time.time() >= self._expires_at:
            self.fetches += 1
            self._token = f"minted-{self.fetches}"
            self._expires_at = time.time() + 900
        return self._token


class _StubClient:
    """Single-spec facade shape: client.api_client.configuration._token_manager"""

    def __init__(self, tm: _StubTM) -> None:
        cfg = type("Cfg", (), {"_token_manager": tm})()
        self.api_client = type("AC", (), {"configuration": cfg})()


def test_session_seed_persist_invalidate(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module(
            "fakesdk_cli._generated.config"
        ).load_config.cache_clear()
        tm = _StubTM()
        client = _StubClient(tm)
        assert ac.token_manager(client) is tm  # resolver finds single-spec shape
        # 1st run: cache miss -> no seed; a fetch happens; persist writes it
        s1 = ac.session(client)
        s1.seed_if_valid()
        assert s1.seeded is False
        tm.token()  # simulate the API call fetching
        s1.persist()
        key = ac.key_for(tm)
        assert ac.read(key) is not None
        # 2nd run: fresh TM, cache hit -> seed, NO fetch on token()
        tm2 = _StubTM()
        s2 = ac.session(_StubClient(tm2))
        s2.seed_if_valid()
        assert s2.seeded is True and tm2._token is not None
        assert tm2.token() == tm2._token and tm2.fetches == 0
        # invalidate clears the file + the in-memory token
        s2.invalidate()
        assert ac.read(key) is None and tm2._token is None


def test_token_manager_resolver_fails_open(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        assert ac.token_manager(object()) is None  # unrecognized shape -> None
        assert ac.session(object()) is None


def _set_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    # _client() validates these (unprefixed) BEFORE _facade_from_env is reached;
    # without them the command exits 2 and the cache code never runs.
    monkeypatch.setenv("CLIENT_ID", "cid")
    monkeypatch.setenv("CLIENT_SECRET", "sec")
    monkeypatch.setenv("SCOPE", "scope-x")


def _fake_facade_with_tm(
    recorder: list[Any], tm: _StubTM, fail_first_status: int | None = None
) -> tuple[Any, Any]:
    """A fake facade whose object attrs record calls AND drive the TokenManager
    the way the real SDK does (each call reads configuration.access_token ->
    tm.token()). The api_client.configuration exposes the stub TM the cache couples
    to. The first call optionally raises the REAL sdk exception class with
    `.status = fail_first_status` so runtime's `except _sdk_exc(cmd)` catches it."""
    import fakesdk.exceptions as _exc_mod
    import fakesdk.extras.facade as facade

    class _Rec:
        def __getattr__(self, name: str) -> Any:
            def _call(*, all_pages: bool = False, **kw: Any) -> Any:
                tm.token()  # the SDK reads the token on every call
                recorder.append((name, kw))
                seen = len([r for r in recorder if r[0] == name])
                if fail_first_status and seen == 1:
                    exc = _exc_mod.OpenApiException(str(fail_first_status))
                    exc.status = fail_first_status
                    raise exc
                return {"id": kw.get("id", "new")}

            return _call

    cfg = type("Cfg", (), {"_token_manager": tm})()
    client = type(
        "Client",
        (),
        {
            "api_client": type("AC", (), {"configuration": cfg})(),
            "widget": _Rec(),
            "gizmo": _Rec(),
            "thing": _Rec(),
        },
    )()
    return facade, client


def test_runtime_reuses_token_across_runs(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    _set_creds(monkeypatch)
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli._generated.runtime")
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module(
            "fakesdk_cli._generated.config"
        ).load_config.cache_clear()
        main = importlib.import_module("fakesdk_cli.main")
        tm = _StubTM()
        rec: list[Any] = []
        _, client = _fake_facade_with_tm(rec, tm)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client)
        r = CliRunner()
        # run 1: cache miss -> the call fetches once, token persisted to disk
        assert r.invoke(main.app, ["show", "widget", "--id", "1"]).exit_code == 0
        assert tm.fetches == 1
        assert ac.read(ac.key_for(tm)) is not None  # persisted
        # run 2: fresh TM seeded from cache -> zero fetches (genuine reuse proof:
        # an unseeded tm2._token would be None -> token() would fetch)
        tm2 = _StubTM()
        rec2: list[Any] = []
        _, client2 = _fake_facade_with_tm(rec2, tm2)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client2)
        assert r.invoke(main.app, ["show", "widget", "--id", "1"]).exit_code == 0
        assert tm2.fetches == 0  # reused the cached token, no grant


def test_runtime_401_invalidates_and_retries_once(
    emit_cli: Callable[..., Path],
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from typer.testing import CliRunner

    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    _set_creds(monkeypatch)
    with render_and_import(out, "fakesdk_cli"):
        rt = importlib.import_module("fakesdk_cli._generated.runtime")
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module(
            "fakesdk_cli._generated.config"
        ).load_config.cache_clear()
        main = importlib.import_module("fakesdk_cli.main")
        tm = _StubTM()
        # seeded-but-rejected token
        ac.write(ac.key_for(tm), "stale", time.time() + 900)
        rec: list[Any] = []
        _, client = _fake_facade_with_tm(rec, tm, fail_first_status=401)
        monkeypatch.setattr(rt, "_facade_from_env", lambda **kw: client)
        res = CliRunner().invoke(main.app, ["show", "widget", "--id", "1"])
        assert res.exit_code == 0  # retried after invalidation
        assert len([r for r in rec if r[0] == "get"]) == 2  # one 401 + one success
        assert ac.read(ac.key_for(tm)) is not None  # re-cached the fresh token


def test_cache_commands(emit_cli, render_and_import, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    out = emit_cli(auth=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    with render_and_import(out, "fakesdk_cli"):
        ac = importlib.import_module("fakesdk_cli._generated.auth_cache")
        importlib.import_module("fakesdk_cli._generated.config").load_config.cache_clear()
        ac.write(ac._key("u", "c", "s"), "secret-token", time.time() + 600)
        main = importlib.import_module("fakesdk_cli.main")
        r = CliRunner()
        show = r.invoke(main.app, ["show", "cli", "cache"])
        assert show.exit_code == 0
        assert "secret-token" not in show.output          # never leak the token
        assert ac._key("u", "c", "s") in show.output       # shows the key id
        clr = r.invoke(main.app, ["config", "cache-clear"])
        assert clr.exit_code == 0 and "removed 1" in clr.output.lower()
        assert ac.list_entries() == []
