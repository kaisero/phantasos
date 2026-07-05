"""Auth token cache — emitted through the fakesdk CLI (rendered WITH auth)."""

from __future__ import annotations

import importlib
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
