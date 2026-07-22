"""Unit tests for the vendor/render step."""

import ast
import json
import sys
import types
from pathlib import Path

import pytest

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
    sys.modules.update({"_le_pkg": pkg, "_le_pkg.extras": extras, "_le_pkg.exceptions": exc})
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
    exc.body = json.dumps({"_errors": [{"code": "A", "message": "first"}, {"message": "second"}]})
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
    exc.body = json.dumps({"errorResponse": {"error": {"code": "E1", "message": "boom"}}})
    assert mod.error_message(exc) == "E1: boom"


def test_nested_error_without_wrapper_still_works() -> None:
    mod = _exec_extras_errors(_render_nested_error())
    exc = mod.ApiException()
    exc.body = json.dumps({"error": {"message": "plain"}})
    assert mod.error_message(exc) == "plain"


_AUTH_PARAMS = {
    "config_class_name": "SdkConfiguration",
    "base_url": "https://h",
    "token_url": "https://t",
    "client_id_env": "CID",
    "client_secret_env": "CSEC",
    "scope_env": "SCOPE",
    "base_url_env": "BURL",
    "has_retry": False,
}
_GOLDEN_SINGLE = Path(__file__).parent / "golden" / "scm_oauth_single_spec.golden.txt"


def _render_auth(**extra: object) -> str:
    return render._env().get_template("auth/scm_oauth.py.jinja").render(**{**_AUTH_PARAMS, **extra})


def test_federated_auth_emits_bearer_client_and_config_factory() -> None:
    """federated=True appends the transport-level bearer client + config factories."""
    txt = _render_auth(federated=True)
    assert "class _BearerApiClient(ApiClient):" in txt
    assert "def update_params_for_auth" in txt
    # Unconditional bearer at the transport layer (works for posture's empty auth).
    bearer = 'headers["Authorization"] = f"Bearer {self.configuration.access_token}"'
    assert bearer in txt
    assert "def configuration_from_env" in txt
    assert "def configuration_from_credentials" in txt
    # Runtime imported ABSOLUTELY (rev-2 S1) — _auth.py sits at the package root,
    # so `..` would escape it.
    assert "from prisma_access._runtime.api_client import ApiClient" in txt
    assert "from prisma_access._runtime.configuration import Configuration" in txt
    assert "from ..api_client import ApiClient" not in txt
    ast.parse(txt)


def test_single_spec_auth_render_is_byte_identical() -> None:
    """federated unset/false keeps the single-spec extras/auth.py byte-unchanged."""
    golden = _GOLDEN_SINGLE.read_text(encoding="utf-8")
    assert _render_auth() == golden  # default (federated unset)
    assert _render_auth(federated=False) == golden  # explicit false
    # The federated-only surface must NOT leak into single-spec output.
    assert "_BearerApiClient" not in golden
    assert "from ..api_client import ApiClient" in golden


def _make_pkg(tmp_path: Path) -> Path:
    """Create a minimal generated package dir with an api/__init__.py."""
    pkg = tmp_path / "demo"
    api = pkg / "api"
    api.mkdir(parents=True)
    (api / "__init__.py").write_text(
        "# flake8: noqa\nfrom demo.api.things_api import ThingsApi\nfrom demo.api.users_api import UsersApi\n",
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
    (pkg / "api" / "__init__.py").write_text("from acme.api.things_api import ThingsApi\n", encoding="utf-8")
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
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
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
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text("package: acme\noutput: ../../out/acme\nbase_url: b\nfacade: false\n", "utf-8")
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
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nerrors: {type: nested}\nfacade: false\n",
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
    (pkg / "api" / "__init__.py").write_text("from acme.api.things_api import ThingsApi\n", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", "utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\nauth: {type: scm_oauth}\nfacade: true\n",
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

    pkg = tmp_path / "out" / "acme"
    (pkg / "api").mkdir(parents=True)
    (pkg / "api" / "__init__.py").write_text("", encoding="utf-8")
    prod = tmp_path / "products" / "acme"
    (prod / "templates").mkdir(parents=True)
    (prod / "templates" / "x.jinja").write_text("x\n", encoding="utf-8")
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "sdk.yml").write_text(
        "package: acme\noutput: ../../out/acme\nbase_url: b\ninclude: {'../escape.py': ./templates/x.jinja}\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    with pytest.raises(ValueError, match="escapes"):
        render.vendor(pkg, loaded, wrapper_objects=[])


def _emit_resources(real_sdk: Path, tmp_path: Path) -> str:
    """Render extras/resources.py for the REAL prisma-browser wrapper context."""
    from phantasos.generator.opmodel import introspect
    from phantasos.generator.sdk.render import _discover_resources
    from phantasos.generator.sdk.wrapper import build_wrapper_context

    inv = introspect("prisma_browser", real_sdk)
    overrides = load_product("prisma-browser").config.operations
    objects = build_wrapper_context(inv, overrides, _discover_resources(real_sdk / "prisma_browser"))

    pkg = tmp_path / "out" / "prisma_browser"
    (pkg / "api").mkdir(parents=True)
    init = (real_sdk / "prisma_browser" / "api" / "__init__.py").read_text(encoding="utf-8")
    (pkg / "api" / "__init__.py").write_text(init, encoding="utf-8")
    prod = tmp_path / "products" / "pb"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "sdk.yml").write_text(
        "package: prisma_browser\noutput: ../../out/prisma_browser\nbase_url: b\n"
        "pagination: {type: cursor}\nfacade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))
    written = render.vendor(pkg, loaded, wrapper_objects=objects)
    assert "resources.py" in written
    return (pkg / "extras" / "resources.py").read_text(encoding="utf-8")


def test_resources_emitted(real_sdk: Path, tmp_path: Path) -> None:
    src = _emit_resources(real_sdk, tmp_path)
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


def test_resources_multibinding_dispatch_via_select(real_sdk: Path, tmp_path: Path) -> None:
    src = _emit_resources(real_sdk, tmp_path)
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


def test_facade_binds_object_wrappers(real_sdk: Path, tmp_path: Path) -> None:
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

    inv = introspect("prisma_browser", real_sdk)
    overrides = load_product("prisma-browser").config.operations
    objects = build_wrapper_context(inv, overrides, _discover_resources(real_sdk / "prisma_browser"))

    prod = tmp_path / "products" / "pb"
    prod.mkdir(parents=True)
    (prod / "openapi.yml").write_text("openapi: 3.0.0\ninfo: {version: '1'}\npaths: {}\n", encoding="utf-8")
    (prod / "sdk.yml").write_text(
        "package: prisma_browser\noutput: ../../out/prisma_browser\nbase_url: b\n"
        "pagination: {type: cursor}\nfacade: true\n",
        encoding="utf-8",
    )
    loaded = load_product(str(prod / "sdk.yml"))

    extras = real_sdk / "prisma_browser" / "extras"
    backups = {name: (extras / name).read_text(encoding="utf-8") for name in ("facade.py", "resources.py")}
    if str(real_sdk) not in sys.path:
        sys.path.insert(0, str(real_sdk))
    try:
        render.vendor(real_sdk / "prisma_browser", loaded, wrapper_objects=objects)
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
        if str(real_sdk) in sys.path:
            sys.path.remove(str(real_sdk))


def test_composer_emits_client_and_subpackages_registry() -> None:
    """The composer renders one Client, the shared-pool wiring, and _SUBPACKAGES."""
    # The sdk package re-exports the build() function (shadowing the build module
    # as an attribute), so import the helper from the module path directly.
    from phantasos.generator.sdk.build import _render_composer

    txt = _render_composer(
        ["objects", "network_services", "ztna_connector"],
        root_package="prisma_access",
        config_class_name="SdkConfiguration",
    )
    assert "_SUBPACKAGES = {" in txt
    assert '"objects":' in txt
    assert "class Client" in txt
    # Lazy handles: each sub is a `cached_property` built on first access (NOT an
    # eager `self.objects = ...` in __init__) so an objects-only call never
    # constructs incidents/ztna_connector.
    assert "from functools import cached_property" in txt
    assert "@cached_property" in txt
    assert "def objects(self)" in txt
    assert "self.objects =" not in txt
    assert "rest_client" in txt  # shared pool wiring
    assert ".models = _objects_models" in txt  # rev-2 B1 instance attr
    assert "configuration_from_env" in txt  # auth config factory
    # Renders to valid Python (no Jinja syntax slips through).
    ast.parse(txt)
    # No default_headers passed -> no `import os`, no apply loop (single-spec /
    # header-less federated products are unaffected).
    assert "import os" not in txt
    assert "default_headers" not in txt


def test_composer_handles_are_lazy_first_access() -> None:
    """Each sub-package handle is built LAZILY on first access (cached_property),
    the required-header raise lives INSIDE the per-sub builder (not __init__), and
    retry wiring is order-independent (no facade is constructed in __init__, so no
    sub is privileged as "first")."""
    from phantasos.generator.sdk.build import _render_composer

    txt = _render_composer(
        ["objects", "incidents", "ztna_connector"],
        root_package="prisma_access",
        config_class_name="SdkConfiguration",
        headers=[
            {
                "name": "X-PANW-Region",
                "env": "PANW_REGION",
                "required": False,
                "required_for": ["incidents", "ztna_connector"],
                "declared_by": ["incidents", "ztna_connector"],
            },
        ],
    )
    # 1. Every sub is a cached_property builder.
    for slug in ("objects", "incidents", "ztna_connector"):
        assert f"def {slug}(self)" in txt
    assert txt.count("@cached_property") == 3

    # 2. No handle is built in __init__ -> the FIRST `_BearerApiClient(` (i.e. any
    #    facade construction) appears only after the first `@cached_property`. With
    #    nothing privileged as "first sub", whichever sub-facade is ACCESSED first
    #    wires retry idempotently onto the shared config -> order-independent.
    assert txt.index("@cached_property") < txt.index("_BearerApiClient(")
    assert "self.incidents =" not in txt and "self.ztna_connector =" not in txt

    # 3. The required-header raise is INSIDE the per-sub builder (after its `def`),
    #    so constructing the Client never reads the header — only touching the sub
    #    does.
    inc = txt.index("def incidents(self)")
    nxt = txt.index("def ", inc + len("def incidents(self)"))
    # the required-header raise sits BETWEEN incidents' def and the next method def
    # — i.e. genuinely inside the incidents builder, not merely somewhere after.
    assert "raise RuntimeError" in txt[inc:nxt]
    ast.parse(txt)


def test_composer_emits_default_header_apply_and_required_for_guard() -> None:
    """default_headers render an env-sourced apply ONLY on subs whose spec declares
    the header (spec-driven scoping via `declared_by`) + a fail-loud guard on the
    slug a header is `required_for`."""
    from phantasos.generator.sdk.build import _render_composer

    txt = _render_composer(
        ["objects", "incidents"],
        root_package="prisma_access",
        config_class_name="SdkConfiguration",
        headers=[
            {
                "name": "X-PANW-Region",
                "env": "PANW_REGION",
                "required": False,
                "required_for": ["incidents"],
                "declared_by": ["incidents"],  # objects never declares it
            },
            {
                "name": "prisma-tenant",
                "env": "PRISMA_TENANT",
                "required": False,
                "required_for": [],
                "declared_by": ["incidents"],
            },
        ],
    )
    assert "import os" in txt
    assert 'os.environ.get("PANW_REGION")' in txt
    assert 'os.environ.get("PRISMA_TENANT")' in txt
    # Header is set on the ApiClient handle's .default_headers (rev-2 B6), not config.
    assert '_ac_incidents.default_headers["X-PANW-Region"] = _v' in txt
    # spec-driven scoping: objects does NOT declare X-PANW-Region -> no apply emitted.
    assert '_ac_objects.default_headers["X-PANW-Region"]' not in txt
    # required_for guard: incidents raises a clear RuntimeError naming env + sub.
    assert "raise RuntimeError(" in txt
    assert "'incidents' is unset" in txt
    assert "set the PANW_REGION environment variable" in txt
    # objects is NOT required_for X-PANW-Region -> no raise for it.
    assert "'objects' is unset" not in txt
    # prisma-tenant is optional everywhere -> never raises.
    assert "PRISMA_TENANT environment variable" not in txt
    ast.parse(txt)


def test_composer_emits_per_sub_host_override() -> None:
    """A sub on a different gateway gets a host-overridden config copy (sharing the
    TokenManager + pool); others use the shared configuration."""
    from phantasos.generator.sdk.build import _render_composer

    txt = _render_composer(
        ["objects", "ztna_connector"],
        root_package="prisma_access",
        config_class_name="SdkConfiguration",
        host_overrides={"ztna_connector": "https://api.sase.paloaltonetworks.com"},
    )
    assert "import copy" in txt
    # ztna_connector: copied config with the override host, handle built from the copy
    assert "_cfg_ztna_connector = copy.copy(configuration)" in txt
    assert '_cfg_ztna_connector.host = "https://api.sase.paloaltonetworks.com"' in txt
    assert "_ac_ztna_connector = _BearerApiClient(_cfg_ztna_connector)" in txt
    # objects: shared configuration, no copy
    assert "_ac_objects = _BearerApiClient(configuration)" in txt
    assert "_cfg_objects" not in txt
    ast.parse(txt)


def test_composer_no_copy_import_when_no_host_overrides() -> None:
    """No host overrides -> no `import copy` (would be an unused import)."""
    from phantasos.generator.sdk.build import _render_composer

    txt = _render_composer(
        ["objects"],
        root_package="prisma_access",
        config_class_name="SdkConfiguration",
    )
    assert "import copy" not in txt
    assert "_ac_objects = _BearerApiClient(configuration)" in txt
    ast.parse(txt)
