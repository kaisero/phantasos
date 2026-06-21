"""Unit tests for the vendor/render step."""

import json
import sys
import types
from pathlib import Path

from phantasos.generator.sdk import render
from phantasos.productconfig import load_product

_EXC_NAMES = (
    "ApiException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "RateLimitException",
    "ServiceException",
)


def _render_list_error(**overrides: str) -> str:
    env = render._env()
    params: dict[str, str] = {
        "errors_field": "_errors",
        "message_field": "message",
        "code_field": "code",
        "request_id_field": "_request_id",
    }
    params.update(overrides)
    return env.get_template("errors/list_error.py.jinja").render(**params)


def _exec_extras_errors(src: str) -> types.ModuleType:
    """Exec a rendered ``extras/errors.py`` inside a stub package so its
    ``from ..exceptions import ...`` resolves; return the module."""
    pkg = types.ModuleType("_le_pkg")
    pkg.__path__ = []
    extras = types.ModuleType("_le_pkg.extras")
    extras.__path__ = []
    exc = types.ModuleType("_le_pkg.exceptions")
    for name in _EXC_NAMES:
        setattr(exc, name, type(name, (Exception,), {"body": None, "data": None}))
    sys.modules.update(
        {"_le_pkg": pkg, "_le_pkg.extras": extras, "_le_pkg.exceptions": exc}
    )
    try:
        mod = types.ModuleType("_le_pkg.extras.errors")
        mod.__package__ = "_le_pkg.extras"
        exec(compile(src, "errors.py", "exec"), mod.__dict__)  # noqa: S102
        return mod
    finally:
        for key in ("_le_pkg", "_le_pkg.extras", "_le_pkg.exceptions"):
            sys.modules.pop(key, None)


def test_list_error_reexports_full_surface() -> None:
    src = _render_list_error()
    for name in (*_EXC_NAMES, "error_message"):
        assert name in src  # F6: extras/__init__.py imports this fixed name list


def test_list_error_message_formats_single_entry() -> None:
    mod = _exec_extras_errors(_render_list_error())
    exc = mod.ApiException()
    exc.body = json.dumps(
        {
            "_errors": [{"code": "API_I00035", "message": "Invalid Request Payload"}],
            "_request_id": "eb18eb0c",
        }
    )
    # code: message, and the request_id is NOT leaked into the human line
    assert mod.error_message(exc) == "API_I00035: Invalid Request Payload"


def test_list_error_message_joins_multiple_and_handles_missing_code() -> None:
    mod = _exec_extras_errors(_render_list_error())
    exc = mod.ApiException()
    exc.body = json.dumps(
        {"_errors": [{"code": "A", "message": "first"}, {"message": "second"}]}
    )
    assert mod.error_message(exc) == "A: first; second"


def test_list_error_message_falls_back_to_top_level() -> None:
    mod = _exec_extras_errors(_render_list_error())
    exc = mod.ApiException()
    exc.body = json.dumps({"message": "top-level message"})
    assert mod.error_message(exc) == "top-level message"


def test_list_error_message_ignores_gateway_msg() -> None:
    # C3: the SCM gateway's {"msg": ...} 403 is a transport shape, NOT posture's
    # documented `_errors[]` schema — so the list_error component does NOT surface
    # it (the CLI's generic fallback tier owns `msg`). It falls through to reason.
    mod = _exec_extras_errors(_render_list_error())
    exc = mod.ApiException()
    exc.body = json.dumps({"msg": "Access denied"})
    assert mod.error_message(exc) == "request failed"


def _render_nested_error(**overrides: object) -> str:
    env = render._env()
    params: dict[str, object] = {
        "error_field": "error",
        "message_field": "message",
        "code_field": "code",
        "wrappers": ["errorResponse", "error_response"],
    }
    params.update(overrides)
    return env.get_template("errors/nested_error.py.jinja").render(**params)


def test_nested_error_unwraps_configured_wrapper() -> None:
    # The wrapper is now documented config; the SDK helper unwraps it too (fixing
    # the prior CLI/SDK divergence where only the CLI peeled errorResponse).
    mod = _exec_extras_errors(_render_nested_error())
    exc = mod.ApiException()
    exc.body = json.dumps(
        {"errorResponse": {"error": {"code": "E1", "message": "boom"}}}
    )
    assert mod.error_message(exc) == "E1: boom"


def test_nested_error_without_wrapper_still_works() -> None:
    mod = _exec_extras_errors(_render_nested_error())
    exc = mod.ApiException()
    exc.body = json.dumps({"error": {"message": "plain"}})
    assert mod.error_message(exc) == "plain"


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
    written = render.vendor(pkg, loaded)

    assert set(written) == {
        "auth.py",
        "pagination.py",
        "errors.py",
        "facade.py",
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
    written = render.vendor(pkg, loaded)

    assert set(written) == {"facade.py", "retry.py", "__init__.py"}
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
    render.vendor(pkg, loaded)
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
        render.vendor(pkg, loaded)
