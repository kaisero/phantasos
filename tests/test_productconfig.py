"""Tests for sdk.yml parsing, validation, and the loader."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from phantasos.config import OAuthClientCredentials
from phantasos.productconfig import (
    Hoist,
    ProductConfig,
    TagOperation,
    Transforms,
    load_product,
    resolve_component,
)


def test_productconfig_minimal() -> None:
    cfg = ProductConfig(package="acme", output="../acme-sdk", base_url="https://api/")
    assert cfg.library == "urllib3"
    assert cfg.apply_generic_patches is True
    assert cfg.transforms == Transforms()


def test_transforms_parse() -> None:
    cfg = ProductConfig.model_validate(
        {
            "package": "acme",
            "output": "../acme-sdk",
            "base_url": "https://api/",
            "transforms": {
                "hoist": [{"schema": "S", "field": "f", "item": "I"}],
                "tag_operations": [
                    {"path": "/x", "method": "get", "operation_id": "GetX", "tag": "X"}
                ],
            },
        }
    )
    assert cfg.transforms.hoist == [Hoist(schema="S", field="f", item="I")]
    assert cfg.transforms.tag_operations[0] == TagOperation(
        path="/x", method="get", operation_id="GetX", tag="X"
    )


def test_unknown_top_level_key_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConfig.model_validate(
            {"package": "a", "output": "o", "base_url": "b", "pagintion": {}}  # typo
        )


def test_resolve_builtin_auth() -> None:
    from phantasos.config import BUILTIN_AUTH

    c = resolve_component(
        {"type": "oauth_client_credentials", "token_url": "https://t/"},
        BUILTIN_AUTH,
        base_dir=Path(),
    )
    assert isinstance(c, OAuthClientCredentials)
    assert c.token_url == "https://t/"


def test_resolve_custom_path(tmp_path: Path) -> None:
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


def test_resolve_missing_custom_path(tmp_path: Path) -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match="template not found"):
        resolve_component(
            {"type": "./templates/missing.jinja"}, BUILTIN_AUTH, base_dir=tmp_path
        )


def test_resolve_unknown_builtin() -> None:
    from phantasos.config import BUILTIN_AUTH

    with pytest.raises(ValueError, match=r"unknown.*type"):
        resolve_component({"type": "magic"}, BUILTIN_AUTH, base_dir=Path())


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
    assert isinstance(loaded.auth, OAuthClientCredentials)
    assert loaded.auth.token_url == "https://t/"
    assert loaded.context["spec_version"] == "9.9.9"
    assert loaded.context["spec_title"] == "Acme"
    assert loaded.context["package"] == "acme"
    assert loaded.context["support_email"] == "sdk@example.com"
    assert loaded.context["has_auth"] is True


def test_load_product_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_product(tmp_path)
    monkeypatch.chdir(tmp_path)
    loaded = load_product("acme")
    assert loaded.config.package == "acme"


def test_load_product_missing_include_source(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\n"
        "include: {x.py: ./templates/nope.jinja}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"template not found|not found"):
        load_product(str(d / "sdk.yml"))


def test_vars_collision_is_error(tmp_path: Path) -> None:
    d = _make_product(tmp_path)
    # A vars key that shadows an auto-exposed name (`package`) must error.
    (d / "sdk.yml").write_text(
        "package: acme\noutput: o\nbase_url: b\nvars: {package: oops}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"shadow|reserved"):
        load_product(str(d / "sdk.yml"))


from phantasos.productconfig import ProjectConfig  # noqa: E402


def test_project_defaults() -> None:
    p = ProjectConfig(
        distribution="acme-sdk",
        author="A",
        author_email="a@b.c",
        repo_url="https://github.com/x/acme-sdk",
    )
    assert p.license == "Apache-2.0"
    assert p.python_versions == ["3.11", "3.12", "3.13", "3.14"]
    assert "pydantic >= 2.11" in p.dependencies


def test_retry_default_on(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n", "utf-8"
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is not None
    assert loaded.context["has_retry"] is True
    assert loaded.retry.max_retries == 3


def test_retry_disabled(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\nretry: false\n",
        "utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.retry is None
    assert loaded.context["has_retry"] is False


def test_project_block_in_sdk_yml(tmp_path: Path) -> None:
    d = tmp_path / "products" / "acme"
    d.mkdir(parents=True)
    (d / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: '9'}\npaths: {}\n", "utf-8"
    )
    (d / "sdk.yml").write_text(
        "package: acme\noutput: ../acme-sdk\nbase_url: https://api/\n"
        "project: {distribution: acme-sdk, author: A, author_email: a@b.c, "
        "repo_url: https://github.com/x/acme-sdk}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(d / "sdk.yml"))
    assert loaded.config.project is not None
    assert loaded.config.project.distribution == "acme-sdk"
    assert loaded.context["distribution"] == "acme-sdk"
    assert loaded.context["repo_url"] == "https://github.com/x/acme-sdk"
    assert loaded.context["license"] == "Apache-2.0"
