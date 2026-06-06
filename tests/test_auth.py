import time
import pytest
from prisma_browser.extras.auth import TokenManager, PrismaSaseConfiguration, api_client_from_env


class _StubTM(TokenManager):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.fetches = 0
    def _fetch(self):
        self.fetches += 1; self._token = f"TOK{self.fetches}"; self._expires_at = time.time() + 840


def test_token_cached():
    tm = _StubTM("id", "sec", "tsg_id:1")
    assert tm.token() == "TOK1" and tm.token() == "TOK1" and tm.fetches == 1


def test_token_refresh_on_expiry():
    tm = _StubTM("id", "sec", "tsg_id:1")
    tm.token(); tm._expires_at = 0
    assert tm.token() == "TOK2" and tm.fetches == 2


def test_configuration_access_token_property():
    tm = _StubTM("id", "sec", "tsg_id:1")
    cfg = PrismaSaseConfiguration(token_manager=tm)
    assert cfg.host == "https://api.sase.paloaltonetworks.com"
    assert cfg.auth_settings()["BearerAuth"]["value"] == "Bearer TOK1"


def test_from_env_missing_vars(monkeypatch):
    for v in ("CLIENT_ID", "CLIENT_SECRET", "SCOPE"):
        monkeypatch.delenv(v, raising=False)
    with pytest.raises(RuntimeError) as e:
        api_client_from_env()
    assert "CLIENT_ID" in str(e.value) and "SCOPE" in str(e.value)
