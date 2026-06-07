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


import textwrap  # noqa: E402
from pathlib import Path  # noqa: E402

from phantasos.productconfig import load_product  # noqa: E402

_SDK_YML = """\
package: acme
output: ../acme-sdk
base_url: https://api.example.com
auth: {type: oauth_client_credentials, token_url: "https://t/"}
pagination: {type: cursor}
errors: {type: nested}
facade: true
vars: {support_email: sdk@example.com}
"""

_OPENAPI = """\
openapi: 3.0.0
info: {title: Acme, version: 9.9.9}
paths: {}
"""


def _make_product(root: Path) -> Path:
    d = root / "products" / "acme"
    d.mkdir(parents=True)
    (d / "sdk.yml").write_text(_SDK_YML, encoding="utf-8")
    (d / "openapi.yml").write_text(_OPENAPI, encoding="utf-8")
    return d


def test_load_product_by_path(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.config.package == "acme"
    assert loaded.auth.token_url == "https://t/"
    assert loaded.context["spec_version"] == "9.9.9"
    assert loaded.context["spec_title"] == "Acme"
    assert loaded.context["package"] == "acme"
    assert loaded.context["support_email"] == "sdk@example.com"
    assert loaded.context["has_auth"] is True


def test_load_product_by_name(tmp_path: Path, monkeypatch: "pytest.MonkeyPatch") -> None:
    _make_product(tmp_path)
    monkeypatch.chdir(tmp_path)
    loaded = load_product("acme")
    assert loaded.config.package == "acme"


def test_vars_collision_is_error(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    # A vars key that shadows an auto-exposed name (`package`) must error.
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\nvars: {package: oops}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="shadow|reserved"):
        load_product(str(d / "sdk.yml"))
