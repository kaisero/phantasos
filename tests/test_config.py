"""Tests for the pydantic component models."""

import pytest
from pydantic import ValidationError

from phantasos.config import (
    BUILTIN_ERRORS,
    BUILTIN_PAGINATION,
    CursorPagination,
    Facade,
    ListError,
    NestedError,
    OffsetPagination,
    ScmOAuth,
)


def test_scm_oauth_defaults_and_template() -> None:
    a = ScmOAuth(type="scm_oauth")
    assert a.scope_env == "SCOPE"
    assert a.config_class_name == "SdkConfiguration"
    assert a.template == "auth/scm_oauth.py.jinja"
    assert a.token_url == "https://auth.apps.paloaltonetworks.com/oauth2/access_token"


def test_cursor_defaults() -> None:
    p = CursorPagination(type="cursor")
    assert p.data_field == "data" and p.cursor_field == "cursor"
    assert p.template == "pagination/cursor.py.jinja"


def test_offset_defaults() -> None:
    p = OffsetPagination(type="offset")
    assert p.data_field == "data"
    assert p.limit_field == "limit"
    assert p.offset_field == "offset"
    assert p.total_field == "total"
    assert p.default_page_size == 100
    assert p.template == "pagination/offset.py.jinja"


def test_offset_registered() -> None:
    assert BUILTIN_PAGINATION["offset"] is OffsetPagination


def test_list_error_defaults() -> None:
    e = ListError(type="list_error")
    assert e.errors_field == "_errors"
    assert e.message_field == "message"
    assert e.code_field == "code"
    assert e.request_id_field == "_request_id"
    assert e.template == "errors/list_error.py.jinja"


def test_list_error_registered() -> None:
    assert BUILTIN_ERRORS["list_error"] is ListError


def test_nested_error_fields_descriptor() -> None:
    env = NestedError(type="nested").error_fields()
    assert env.error_field == "error"
    assert env.errors_field is None
    assert env.wrappers == ("errorResponse", "error_response")
    assert (env.message_field, env.code_field) == ("message", "code")


def test_list_error_fields_descriptor() -> None:
    env = ListError(type="list_error").error_fields()
    assert env.errors_field == "_errors"
    assert env.error_field is None
    assert env.wrappers == ()
    assert (env.message_field, env.code_field) == ("message", "code")


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
