"""Unit tests for the vendor/render step."""

import ast
import json
import sys
import types
from pathlib import Path

import pytest

from phantasos.generator.sdk import render
from phantasos.productconfig import load_product

_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
_PKG = _SDK / "prisma_browser"

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
    # facade retains the raw `_RESOURCES` map (introspection target) and
    # references the auth/pagination modules
    facade_src = (extras / "facade.py").read_text(encoding="utf-8")
    assert '"things": ThingsApi' in facade_src
    assert "_RESOURCES = {" in facade_src and "_WRAPPERS = {" in facade_src
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
    assert '"things": ThingsApi' in facade_src


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
    # Every generated method carries a one-line docstring.
    assert '"""Get a' in src or '"""List' in src or '"""Create' in src
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


def _purge_pb_extras() -> None:
    """Drop any cached ``prisma_browser.extras{,.facade,.resources}`` modules.

    Both this helper and ``vendor`` rewrite ``facade.py``/``resources.py`` on the
    REAL package on disk, so a later import must re-read the new files, never the
    stale cache.
    """
    import sys

    for name in list(sys.modules):
        if name == "prisma_browser.extras" or name.startswith("prisma_browser.extras."):
            del sys.modules[name]


@pytest.mark.skipif(not _SDK.exists(), reason="prisma-browser SDK not built")
def test_facade_binds_object_wrappers(tmp_path: Path) -> None:
    """Two-pass facade: ``client.<object>`` is a typed wrapper, raw ``*Api`` hidden.

    Vendors the full two-pass facade into the REAL package (so the emitted
    relative/absolute imports resolve) and restores the two touched files after.
    Asserts the wrapper surface, the shared ``*Api`` across sibling objects, and
    that BOTH ``_RESOURCES`` (raw map, introspection target) and ``_WRAPPERS``
    (object map) live on the facade module.
    """
    import importlib
    import sys

    from phantasos.generator.opmodel import introspect
    from phantasos.generator.sdk.render import _discover_resources
    from phantasos.generator.sdk.wrapper import build_wrapper_context

    inv = introspect("prisma_browser", _SDK)
    overrides = load_product("prisma-browser").config.operations
    objects = build_wrapper_context(inv, overrides, _discover_resources(_PKG))

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

    extras = _PKG / "extras"
    backups = {
        name: (extras / name).read_text(encoding="utf-8")
        for name in ("facade.py", "resources.py")
    }
    if str(_SDK) not in sys.path:
        sys.path.insert(0, str(_SDK))
    try:
        render.vendor(_PKG, loaded, wrapper_objects=objects)
        _purge_pb_extras()
        facade = importlib.import_module("prisma_browser.extras.facade")

        class _FakeApiClient:
            configuration = type("C", (), {"retries": object()})()

        client = facade.Client(_FakeApiClient())

        # client.<object> is the typed wrapper, exposing clean verbs only.
        assert type(client.application).__name__ == "ApplicationResource"
        assert hasattr(client.application, "create")
        assert not hasattr(client.application, "create_application")
        assert not hasattr(client.application, "get_application_by_id")
        # The raw *Api is held privately on the wrapper, not on the client.
        assert not hasattr(client, "applications")
        assert client.application._api.__class__.__name__ == "ApplicationsApi"
        # Sibling objects backed by one *Api class SHARE the *Api instance.
        assert client.access_and_data_rule._api is client.access_and_data_section._api
        # Both maps live on the module; _RESOURCES is the raw introspection target.
        assert "applications" in facade._RESOURCES
        assert "application" in facade._WRAPPERS
        assert facade._WRAPPERS["application"][0] is type(client.application)
        # The single HTTP-capture point is still exposed.
        assert client.api_client is not None
    finally:
        for name, text in backups.items():
            (extras / name).write_text(text, encoding="utf-8")
        _purge_pb_extras()
        if str(_SDK) in sys.path:
            sys.path.remove(str(_SDK))
