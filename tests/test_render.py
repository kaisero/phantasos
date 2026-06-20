"""Unit tests for the vendor/render step."""

import ast
from pathlib import Path

import pytest

from phantasos.generator.sdk import render
from phantasos.productconfig import load_product

_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
_PKG = _SDK / "prisma_browser"


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
        "  type: scm_oauth\n"
        "  config_class_name: DemoConfiguration\n"
        "pagination:\n"
        "  type: cursor\n"
        "errors:\n"
        "  type: nested\n"
        "facade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded, wrapper_objects=[])

    assert set(written) == {
        "auth.py",
        "pagination.py",
        "errors.py",
        "facade.py",
        "resources.py",
        "retry.py",
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
    written = render.vendor(pkg, loaded, wrapper_objects=[])

    assert set(written) == {"facade.py", "resources.py", "retry.py", "__init__.py"}
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
    written = render.vendor(pkg, loaded, wrapper_objects=[])
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


def test_vendor_writes_retry(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nfacade: false\n", "utf-8"
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded)
    assert "retry.py" in written
    src = (pkg / "extras" / "retry.py").read_text()
    assert "class JitteredRetry" in src and "def default_retry" in src
    assert "status_forcelist=[408, 429, 500, 502, 503, 504]" in src
    import ast

    ast.parse(src)


def test_errors_exports_ratelimit_not_helper(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\n"
        "errors: {type: nested}\nfacade: false\n",
        "utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    render.vendor(pkg, loaded)
    src = (pkg / "extras" / "errors.py").read_text()
    assert "RateLimitException" in src
    assert "is_rate_limited" not in src


def test_auth_and_facade_use_default_retry(tmp_path: Path) -> None:
    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text(
        "from acme.api.things_api import ThingsApi\n", encoding="utf-8"
    )
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\n"
        "auth: {type: scm_oauth}\n"
        "facade: true\n",
        "utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    render.vendor(pkg, loaded, wrapper_objects=[])
    auth_src = (pkg / "extras" / "auth.py").read_text()
    facade_src = (pkg / "extras" / "facade.py").read_text()
    assert "from .retry import default_retry" in auth_src
    assert "default_retry()" in auth_src
    assert "from .retry import default_retry" in facade_src
    assert "default_retry()" in facade_src
    import ast

    ast.parse(auth_src)
    ast.parse(facade_src)


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
        render.vendor(pkg, loaded, wrapper_objects=[])


def _emit_resources(tmp_path: Path) -> str:
    """Render extras/resources.py for the REAL prisma-browser wrapper context."""
    from phantasos.generator.opmodel import introspect
    from phantasos.generator.sdk.render import _discover_resources
    from phantasos.generator.sdk.wrapper import build_wrapper_context

    inv = introspect("prisma_browser", _SDK)
    overrides = load_product("prisma-browser").config.operations
    objects = build_wrapper_context(inv, overrides, _discover_resources(_PKG))

    pkg = tmp_path / "out" / "prisma_browser"
    (pkg / "api").mkdir(parents=True)
    init = (_PKG / "api" / "__init__.py").read_text(encoding="utf-8")
    (pkg / "api" / "__init__.py").write_text(init, encoding="utf-8")
    prod = tmp_path / "products" / "pb"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text(
        "openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8"
    )
    (prod / "sdk.yml").write_text(
        "package: prisma_browser\noutput: ../../out/prisma_browser\nbase_url: b\n"
        "pagination: {type: cursor}\nfacade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded, wrapper_objects=objects)
    assert "resources.py" in written
    return (pkg / "extras" / "resources.py").read_text(encoding="utf-8")


@pytest.mark.skipif(not _SDK.exists(), reason="prisma-browser SDK not built")
def test_resources_emitted(tmp_path: Path) -> None:
    src = _emit_resources(tmp_path)
    # Typed wrapper class named <Object>Resource (NOT <Object>WrapperResource).
    assert "class ApplicationResource" in src
    assert "WrapperResource" not in src
    # The dumb-template seams: _bindings table + generated _serialize twin.
    assert "_bindings: ClassVar" in src
    assert "def _serialize(self" in src
    # all_pages toggle on list + the page-rewrap (not a hard-coded total/offset).
    assert "all_pages: bool = False" in src
    assert "model_copy(update=" in src
    # Raw method names live ONLY inside _bindings / dispatch — never as public defs.
    assert "def get_application_by_id" not in src
    assert "def list_applications" not in src
    assert "'raw_method': 'get_application_by_id'" in src
    # Parses clean.
    ast.parse(src)


@pytest.mark.skipif(not _SDK.exists(), reason="prisma-browser SDK not built")
def test_resources_multibinding_dispatch_via_select(tmp_path: Path) -> None:
    src = _emit_resources(tmp_path)
    # application.list collapses two raw ops; the by-type op routes `type` to path,
    # the plain op to query — both must appear in _bindings so _select can choose.
    assert "'raw_method': 'list_applications'" in src
    assert "'raw_method': 'list_applications_by_type'" in src
    # Multi-binding list/get/delete dispatch through _select, not bindings[0].
    assert "def _select(self" in src
    assert 'max(cands, key=lambda b: len(b["requires"]))' in src
    # The list method delegates to the generic _list helper (with all_pages).
    assert 'return self._list("list"' in src
    # A returning get unwraps via _fetch; a delete (no return) via _call.
    assert 'return self._fetch("get"' in src
    assert 'return self._call("delete"' in src
