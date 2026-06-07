"""Unit tests for SdkConfig component selection/ordering."""

from sdkgen.config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
    SdkConfig,
)


def test_components_full_order() -> None:
    auth = OAuthClientCredentials(token_url="https://t/")
    pagination = CursorPagination()
    errors = NestedError()
    facade = Facade()
    cfg = SdkConfig(
        spec="s.yml",
        package="pkg",
        base_url="https://api/",
        auth=auth,
        pagination=pagination,
        errors=errors,
        facade=facade,
    )
    # auth, pagination, errors, facade — in that order.
    assert cfg.components() == [auth, pagination, errors, facade]


def test_components_skips_none() -> None:
    cfg = SdkConfig(
        spec="s.yml",
        package="pkg",
        base_url="https://api/",
        auth=None,
        pagination=None,
        errors=None,
    )
    # facade defaults to a Facade() instance via default_factory.
    components = cfg.components()
    assert len(components) == 1
    assert isinstance(components[0], Facade)


def test_components_facade_only_explicit_none() -> None:
    cfg = SdkConfig(
        spec="s.yml",
        package="pkg",
        base_url="https://api/",
        facade=None,
    )
    assert cfg.components() == []
