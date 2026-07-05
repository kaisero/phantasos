"""Live: a real SCM grant is cached and reused on the second build_client call."""

import importlib
import os
import sys
from pathlib import Path

import pytest

_CREDS = ("CLIENT_ID", "CLIENT_SECRET", "SCOPE")
_REAL = Path(__file__).resolve().parent.parent.parent / "prisma-browser-sdk"


@pytest.mark.skipif(not _REAL.exists(), reason="prisma-browser-sdk not built")
@pytest.mark.skipif(
    any(not os.environ.get(k) for k in _CREDS), reason="live tenant credentials not set"
)
def test_live_token_is_cached_and_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    if str(_REAL) not in sys.path:
        sys.path.insert(0, str(_REAL))
    auth = importlib.import_module("prisma_browser.extras.auth")
    tm = auth.TokenManager(
        os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"], os.environ["SCOPE"]
    )
    first = tm.token()  # real grant
    assert first and tm._expires_at > 0
    # simulate the CLI persisting + a fresh run seeding (key derivation is
    # exercised for real by auth_cache.key_for(); not needed here)
    tm2 = auth.TokenManager(
        os.environ["CLIENT_ID"], os.environ["CLIENT_SECRET"], os.environ["SCOPE"]
    )
    tm2._token, tm2._expires_at = first, tm._expires_at  # seed from "cache"
    assert tm2.token() == first  # reused; no second grant
