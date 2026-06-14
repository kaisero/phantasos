"""Tests for the pydantic component models."""

import pytest
from pydantic import ValidationError

from phantasos.config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
)


def test_oauth_defaults_and_template() -> None:
    a = OAuthClientCredentials(type="oauth_client_credentials", token_url="https://t/")
    assert a.scope_env == "SCOPE"
    assert a.config_class_name == "SdkConfiguration"
    assert a.template == "auth/oauth_client_credentials.py.jinja"


def test_cursor_defaults() -> None:
    p = CursorPagination(type="cursor")
    assert p.data_field == "data" and p.cursor_field == "cursor"
    assert p.template == "pagination/cursor.py.jinja"


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        NestedError.model_validate({"type": "nested", "bogus_key": "x"})


def test_facade_template() -> None:
    assert Facade(type="default").template == "facade/client.py.jinja"


def test_retry_defaults() -> None:
    from phantasos.config import RetryConfig

    r = RetryConfig(type="default")
    assert r.max_retries == 3
    assert r.backoff_base == 0.5
    assert r.backoff_max == 8.0
    assert r.jitter_frac == 0.25
    assert r.statuses == [408, 429, 500, 502, 503, 504]
    assert r.respect_retry_after is True
    assert r.template == "retry/jittered_retry.py.jinja"
