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


# --- Idempotency config models (SDK idempotent-sync, Task 0.1) ---

from phantasos.config import (  # noqa: E402
    IdempotencyConfig,
    IdempotencyResource,
    ScopeSpec,
)


def test_idempotency_config_roundtrips_scoped_example() -> None:
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {
                "scope": {
                    "fields": ["folder", "snippet", "device"],
                    "rule": "exactly_one",
                }
            },
            "resources": {
                "address": {},
                "address_group": {"order_sensitive": ["static"]},
                "auto_tag_action": {"sync": False},
            },
        }
    )
    assert cfg.defaults.scope is not None
    assert cfg.defaults.scope.fields == ["folder", "snippet", "device"]
    assert cfg.resources["address"].sync is True
    assert cfg.resources["address_group"].order_sensitive == ["static"]
    assert cfg.resources["auto_tag_action"].sync is False


def test_idempotency_config_roundtrips_noscope_example() -> None:
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"read_only": ["id", "createdAt", "updatedAt"]},
            "resources": {
                "user_group": {},
                "application": {"identity": ["type", "name"]},
                "application_plugin": {"sync": False},
            },
        }
    )
    assert cfg.defaults.scope is None
    assert cfg.resources["application"].identity == ["type", "name"]


def test_idempotency_resource_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        # typo -> extra=forbid
        IdempotencyResource.model_validate({"identiy": ["name"]})


def test_idempotency_resource_accepts_strategy_override_strings() -> None:
    r = IdempotencyResource.model_validate(
        {
            "fetch": "list_filter",
            "mutate": "patch_minimal",
            "materialize": "get_after_write",
        }
    )
    assert (r.fetch, r.mutate, r.materialize) == (
        "list_filter",
        "patch_minimal",
        "get_after_write",
    )


def test_scope_spec_defaults_rule_exactly_one() -> None:
    assert ScopeSpec.model_validate({"fields": ["folder"]}).rule == "exactly_one"


def test_idempotency_resource_accepts_params_default() -> None:
    r = IdempotencyResource.model_validate({"params": {"position": {"default": "pre"}}})
    assert r.params["position"].default == "pre"
    # default is optional (None -> the param stays call-time-required)
    bare = IdempotencyResource.model_validate({"params": {"position": {}}})
    assert bare.params["position"].default is None


def test_idempotency_param_spec_rejects_derived_facts() -> None:
    # values/verbs are auto-derived by the producer — config may not set them.
    with pytest.raises(ValidationError):
        IdempotencyResource.model_validate({"params": {"position": {"values": ["pre", "post"]}}})
    with pytest.raises(ValidationError):
        IdempotencyResource.model_validate({"params": {"position": {"verbs": ["list"]}}})
