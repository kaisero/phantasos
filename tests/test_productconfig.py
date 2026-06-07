"""Tests for sdk.yml parsing, validation, and the loader."""

import pytest
from pydantic import ValidationError

from phantasos.productconfig import Hoist, ProductConfig, TagOperation, Transforms


def test_productconfig_minimal() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.library == "urllib3"
    assert cfg.apply_generic_patches is True
    assert cfg.transforms == Transforms()


def test_transforms_parse() -> None:
    cfg = ProductConfig(
        package="acme",
        output="../acme-sdk",
        base_url="https://api/",
        transforms={
            "hoist": [{"schema": "S", "field": "f", "item": "I"}],
            "tag_operations": [
                {"path": "/x", "method": "get", "operation_id": "GetX", "tag": "X"}
            ],
        },
    )
    assert cfg.transforms.hoist == [Hoist(schema="S", field="f", item="I")]
    assert cfg.transforms.tag_operations[0] == TagOperation(
        path="/x", method="get", operation_id="GetX", tag="X"
    )


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConfig(
            package="a", output="o", base_url="b", pagintion={}  # typo
        )


from phantasos.config import OAuthClientCredentials  # noqa: E402
from phantasos.productconfig import resolve_component  # noqa: E402


def test_resolve_builtin_auth() -> None:
    from phantasos.config import BUILTIN_AUTH

    c = resolve_component(
        {"type": "oauth_client_credentials", "token_url": "https://t/"},
        BUILTIN_AUTH,
        base_dir=__import__("pathlib").Path("."),
    )
    assert isinstance(c, OAuthClientCredentials)
    assert c.token_url == "https://t/"


def test_resolve_custom_path(tmp_path) -> None:
    from phantasos.config import BUILTIN_AUTH

    tpl = tmp_path / "templates" / "api_key.py.jinja"
    tpl.parent.mkdir(parents=True)
    tpl.write_text("", encoding="utf-8")
    c = resolve_component(
        {"type": "./templates/api_key.py.jinja", "header_name": "X-API-Key"},
        BUILTIN_AUTH,
        base_dir=tmp_path,
    )
    assert c.template == str(tpl)
    assert c.extra["header_name"] == "X-API-Key"


def test_resolve_missing_custom_path(tmp_path) -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="template not found"):
        resolve_component(
            {"type": "./templates/missing.jinja"}, BUILTIN_AUTH, base_dir=tmp_path
        )


def test_resolve_unknown_builtin() -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="unknown.*type"):
        resolve_component(
            {"type": "magic"}, BUILTIN_AUTH, base_dir=__import__("pathlib").Path(".")
        )
