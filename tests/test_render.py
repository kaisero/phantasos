"""Unit tests for the vendor/render step."""

from pathlib import Path

from phantasos.generator.sdk import render
from phantasos.productconfig import load_product


def _make_pkg(tmp_path: Path) -> Path:
    """Create a minimal generated package dir with an api/__init__.py."""
    pkg = tmp_path / "demo"
    api = pkg / "api"
    api.mkdir(parents=True)
    (api / "__init__.py").write_text(
        "# flake8: noqa\n"
        "from demo.api.things_api import ThingsApi\n"
        "from demo.api.users_api import UsersApi\n",
        encoding="utf-8",
    )
    return pkg


def test_discover_resources(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)
    resources = render._discover_resources(pkg)
    assert resources == [
        {"module": "things_api", "cls": "ThingsApi", "attr": "things"},
        {"module": "users_api", "cls": "UsersApi", "attr": "users"},
    ]


def test_vendor_full_components(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)

    prod = tmp_path / "products" / "demo"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Demo, version: 1.0.0}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: demo\n"
        "output: x\n"
        "base_url: https://api.example.com\n"
        "auth:\n"
        "  type: oauth_client_credentials\n"
        "  token_url: 'https://auth/token'\n"
        "  config_class_name: DemoConfiguration\n"
        "pagination:\n"
        "  type: cursor\n"
        "errors:\n"
        "  type: nested\n"
        "facade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)

    assert set(written) == {
        "auth.py",
        "pagination.py",
        "errors.py",
        "facade.py",
        "__init__.py",
    }
    extras = pkg / "extras"
    for name in written:
        assert (extras / name).exists()
    # facade binds the discovered resources and references the auth/pagination modules
    facade_src = (extras / "facade.py").read_text(encoding="utf-8")
    assert "things: ThingsApi" in facade_src
    assert "from .auth import" in facade_src
    # auth template inlined the config class name
    auth_src = (extras / "auth.py").read_text(encoding="utf-8")
    assert "class DemoConfiguration(Configuration):" in auth_src


def test_vendor_facade_only(tmp_path: Path) -> None:
    pkg = _make_pkg(tmp_path)

    prod = tmp_path / "products" / "demo"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Demo, version: 1.0.0}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: demo\noutput: x\nbase_url: https://api.example.com\nfacade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)

    assert set(written) == {"facade.py", "__init__.py"}
    facade_src = (pkg / "extras" / "facade.py").read_text(encoding="utf-8")
    assert "from .auth" not in facade_src
    assert "from .pagination" not in facade_src
    assert "things: ThingsApi" in facade_src


def test_vendor_uses_loaded_product_and_include(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text(
        "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
    )
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "banner.py.jinja").write_text(
        "BANNER = '{{ package }} {{ spec_version }}'\n", encoding="utf-8"
    )
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {title: Acme, version: 1.0.0}\npaths: {}\n",
        encoding="utf-8",
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: https://api/\n"
        "facade: true\ninclude: {banner.py: ./templates/banner.py.jinja}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)
    assert "facade.py" in written
    assert (pkg / "extras" / "banner.py").read_text() == "BANNER = 'acme 1.0.0'\n"


def test_vendor_custom_component_template(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "api_key.py.jinja").write_text(
        "HEADER = '{{ header_name }}'  # {{ package }}\n", encoding="utf-8"
    )
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nfacade: false\n"
        "auth: {type: ./templates/api_key.py.jinja, header_name: X-API-Key}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)
    assert "auth.py" in written
    assert (pkg / "extras" / "auth.py").read_text() == "HEADER = 'X-API-Key'  # acme\n"


def test_include_rejects_path_escape(tmp_path: Path) -> None:
    import pytest

    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "x.jinja").write_text("x\n", encoding="utf-8")
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\n"
        "include: {'../escape.py': ./templates/x.jinja}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    with pytest.raises(ValueError, match="escapes"):
        render.vendor(pkg, loaded)
