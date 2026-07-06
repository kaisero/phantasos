"""Ring-3: auth_cache's coupling matches the REAL prisma-browser SDK.

Renders a prisma-browser CLI (to get the emitted `auth_cache` module) and builds
the REAL facade Client credential-free, so the actual navigation path
`client.api_client.configuration._token_manager` is validated against a real
artifact — the exact fragile coupling D2 accepts. Also proves the real
TokenManager honors a cache-seeded token WITHOUT issuing a grant (stubbed HTTP,
never the real token endpoint).
"""

import importlib
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from phantasos.generator.opmodel._pathutil import on_sys_path


def _render_pb_cli(real_sdk: Path, tmp_path: Path) -> Path:
    """Render a prisma-browser CLI WITH auth into tmp_path; return its package dir.
    Skips if the SDK's runtime deps aren't importable (matches the ring pattern)."""
    from phantasos.config import ScmOAuth
    from phantasos.generator.cli.classify import build_cli_ir, cli_operations
    from phantasos.generator.cli.cliconfig import load_cli_config
    from phantasos.generator.cli.render_cli import render_cli

    try:
        inv = cli_operations("prisma_browser", real_sdk)
    except ImportError as exc:
        pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
    ir, _ = build_cli_ir(inv, load_cli_config(Path("products/prisma-browser/cli.yml")))
    render_cli(
        ir,
        package="prisma_browser_cli",
        out_dir=tmp_path,
        env_prefix="PRISMA",
        distribution="prisma-browser-cli",
        auth=ScmOAuth(type="scm_oauth"),
    )
    return tmp_path


def test_resolver_finds_tm_on_real_facade(
    real_sdk: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    render_and_import: Callable[[Path, str], AbstractContextManager[ModuleType]],
) -> None:
    """auth_cache.token_manager() resolves the TM on the REAL facade Client."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _render_pb_cli(real_sdk, tmp_path)
    with on_sys_path(real_sdk), render_and_import(tmp_path, "prisma_browser_cli"):
        try:
            facade = importlib.import_module("prisma_browser.extras.facade")
            auth = importlib.import_module("prisma_browser.extras.auth")
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk not importable: {exc}")
        ac = importlib.import_module("prisma_browser_cli._generated.auth_cache")
        # credential-free client: no network until a call is made
        client = facade.Client(
            auth.api_client_from_credentials(
                client_id="x", client_secret="y", scope="z"
            )
        )
        tm = ac.token_manager(client)
        assert tm is not None, "resolver failed on the real facade (coupling broke)"
        assert tm is client.api_client.configuration._token_manager
        assert ac.key_for(tm)  # reads _token_url/_client_id/_scope off the real TM


def test_real_tm_honors_seeded_token_without_grant(
    real_sdk: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache-seeded token is returned by the REAL TokenManager with no grant."""
    with on_sys_path(real_sdk):
        try:
            auth = importlib.import_module("prisma_browser.extras.auth")
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk not importable: {exc}")

        class _FakeHTTP:  # stub the token endpoint (external auth server, not the API)
            def __init__(self) -> None:
                self.count = 0

            def request(self, *a: Any, **k: Any) -> None:
                self.count += 1
                raise AssertionError(
                    "a grant was attempted despite a valid seeded token"
                )

        http = _FakeHTTP()
        tm = auth.TokenManager("x", "y", "z", http=http)
        tm._token, tm._expires_at = "cached", time.time() + 900  # seed as the CLI does
        assert tm.token() == "cached" and http.count == 0
        # expired seed -> the real fetch path IS taken (proves expiry handling is real)
        tm._token, tm._expires_at = "old", time.time() - 1
        with pytest.raises(AssertionError, match="grant was attempted"):
            tm.token()
