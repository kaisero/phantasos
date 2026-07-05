"""Auth token cache — emitted through the fakesdk CLI (rendered WITH auth)."""

from __future__ import annotations

import importlib
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType

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
