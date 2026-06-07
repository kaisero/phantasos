"""Unit tests for the vendor/render step."""

from pathlib import Path

from sdkgen import render
from sdkgen.config import (
    CursorPagination,
    Facade,
    NestedError,
    OAuthClientCredentials,
    SdkConfig,
)


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
    cfg = SdkConfig(
        spec="s.yml",
        package="demo",
        base_url="https://api.example.com",
        auth=OAuthClientCredentials(
            token_url="https://auth/token",
            config_class_name="DemoConfiguration",
        ),
        pagination=CursorPagination(),
        errors=NestedError(),
        facade=Facade(),
    )
    written = render.vendor(pkg, cfg)
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
    cfg = SdkConfig(
        spec="s.yml",
        package="demo",
        base_url="https://api.example.com",
        auth=None,
        pagination=None,
        errors=None,
        facade=Facade(),
    )
    written = render.vendor(pkg, cfg)
    assert set(written) == {"facade.py", "__init__.py"}
    facade_src = (pkg / "extras" / "facade.py").read_text(encoding="utf-8")
    assert "from .auth" not in facade_src
    assert "from .pagination" not in facade_src
    assert "things: ThingsApi" in facade_src
