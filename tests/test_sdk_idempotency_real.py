"""Ring-3 real-artifact assertions for the idempotency surface (Task 6.3).

These tests import the ACTUALLY-BUILT sibling SDKs and assert against the emitted
artifacts on disk — the live ``_idempotency`` classvar baked onto each opted-in
``<Object>Resource`` class, the ``SyncMixin`` sync surface (``apply``/``absent``/
``fetch``/``diff``) inherited by those classes with the spec §4.1 signatures, the
vendored ``extras/idempotency/`` strategy tree (union-only: exactly the referenced
strategy modules, nothing else), and the injectable-token ``Client.from_access_token``
factory on both packages.

Distinct from ``test_sdk_idempotency_context.py``, which re-derives the wrapper
*context* from the built models via ``build_wrapper_context`` — a derivation, not
the emitted file. Here we read the artifact the generator actually wrote and a
consumer actually imports.

They SKIP (never fail) when a sibling SDK is not built, so a fresh checkout and
the SDK-less CI ``tests`` job stay quiet; the ``smoke`` session builds them. Each
test carries the ``real_sdk`` marker so the whole ring is selectable with
``-m real_sdk``.
"""

from __future__ import annotations

import importlib
import inspect
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

_REPO_PARENT = Path(__file__).resolve().parent.parent.parent
_ACCESS_SDK = _REPO_PARENT / "prisma-access-sdk"
_BROWSER_SDK = _REPO_PARENT / "prisma-browser-sdk"

# §4.1 sync surface: method name -> (positional-or-keyword params after self,
# keyword-only params, whether it takes **kwargs). Signatures are asserted exactly
# so a drift in the mixin's public shape trips the ring. apply/absent carry
# **params for the extra-required call params (e.g. the rulebase `position`
# enum) — validated against the baked `params` meta, inert without one.
_SYNC_SURFACE = {
    "apply": (["desired"], ["check_mode"], True),  # **params
    "absent": (["desired_or_identity"], ["check_mode"], True),  # **params
    "fetch": ([], [], True),  # **identity_and_scope (+ declared params)
    "diff": (["desired", "actual"], [], False),
}


@pytest.fixture
def browser_pkg() -> Iterator[Any]:
    """The built single-spec prisma-browser package, importable, on sys.path.

    Skips (never fails) when the SDK isn't built or its runtime deps are missing.
    """
    if not (_BROWSER_SDK / "prisma_browser").exists():
        pytest.skip("prisma-browser-sdk not built (run: nox -s smoke)")
    sys.path.insert(0, str(_BROWSER_SDK))
    try:
        try:
            import prisma_browser  # noqa: F401
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        yield importlib.import_module("prisma_browser")
    finally:
        sys.path.remove(str(_BROWSER_SDK))


@pytest.fixture
def access_pkg() -> Iterator[Any]:
    """The built federated prisma-access package, importable, on sys.path.

    Skips (never fails) when the SDK isn't built or its runtime deps are missing.
    """
    if not (_ACCESS_SDK / "prisma_access" / "objects").exists():
        pytest.skip("prisma-access-sdk not built (run: nox -s smoke)")
    sys.path.insert(0, str(_ACCESS_SDK))
    try:
        try:
            import prisma_access  # noqa: F401
        except ImportError as exc:
            pytest.skip(f"prisma-access-sdk runtime deps unavailable: {exc}")
        yield importlib.import_module("prisma_access")
    finally:
        sys.path.remove(str(_ACCESS_SDK))


def _assert_sync_surface(cls: type[Any]) -> None:
    """Every §4.1 method is present with the exact documented signature."""
    for name, (posargs, kwonly, has_var_kw) in _SYNC_SURFACE.items():
        fn = getattr(cls, name, None)
        assert callable(fn), f"{cls.__name__} is missing sync method {name!r}"
        params = list(inspect.signature(fn).parameters.values())
        assert params[0].name == "self"
        rest = params[1:]
        kinds = inspect.Parameter
        pos = [p.name for p in rest if p.kind is kinds.POSITIONAL_OR_KEYWORD]
        kw = [p.name for p in rest if p.kind is kinds.KEYWORD_ONLY]
        var_kw = any(p.kind is kinds.VAR_KEYWORD for p in rest)
        assert pos == posargs, f"{name}: positional params {pos} != {posargs}"
        assert kw == kwonly, f"{name}: keyword-only params {kw} != {kwonly}"
        assert var_kw is has_var_kw, f"{name}: **kwargs presence mismatch"


@pytest.mark.real_sdk
def test_browser_application_group_sync_surface_and_meta(browser_pkg: Any) -> None:
    # The BUILT prisma-browser application_group wrapper: SyncMixin surface with
    # the §4.1 signatures + the PATCH-family strategy trio baked into the live
    # classvar (patch_minimal mutate / get_after_write materialize).
    res = importlib.import_module("prisma_browser.extras.resources")
    cls = res.ApplicationGroupResource
    _assert_sync_surface(cls)
    meta = cls._idempotency
    assert meta["mutate"] == "patch_minimal"
    assert meta["materialize"] == "get_after_write"
    # A PATCH-updatable object keeps the `update` verb (not a full replace).
    assert meta["update"] == {"verb": "update"}
    assert meta["identity"] == ["name"]


@pytest.mark.real_sdk
def test_access_address_meta_and_scope_trio(access_pkg: Any) -> None:
    # The BUILT prisma-access address wrapper carries the PUT-family trio +
    # replace-verb + the folder/snippet/device scope trio in its live classvar.
    res = importlib.import_module("prisma_access.objects.extras.resources")
    cls = res.AddressResource
    _assert_sync_surface(cls)
    meta = cls._idempotency
    assert meta["fetch"] == "list_scan"
    assert meta["mutate"] == "put_rmw"
    assert meta["materialize"] == "direct"
    assert meta["update"] == {"verb": "replace"}
    assert meta["identity"] == ["name"]
    assert meta["scope"]["fields"] == ["folder", "snippet", "device"]


def _strategy_modules(idem_dir: Path) -> dict[str, set[str]]:
    """The per-family set of vendored strategy module stems under *idem_dir*."""
    return {
        family: {
            p.stem for p in (idem_dir / family).glob("*.py") if p.name != "__init__.py"
        }
        for family in ("fetch", "mutate", "materialize")
    }


@pytest.mark.real_sdk
def test_browser_idempotency_tree_is_union_only(browser_pkg: Any) -> None:
    # The vendored tree holds ONLY the strategies the browser SDK's synced
    # resources reference — the PATCH family — and no stray modules.
    idem = _BROWSER_SDK / "prisma_browser" / "extras" / "idempotency"
    assert idem.is_dir()
    assert (idem / "engine.py").exists() and (idem / "base.py").exists()
    assert _strategy_modules(idem) == {
        "fetch": {"list_scan"},
        "mutate": {"patch_minimal"},
        "materialize": {"get_after_write"},
    }


@pytest.mark.real_sdk
def test_access_idempotency_tree_is_union_only(access_pkg: Any) -> None:
    # prisma-access opts in address/tag/address_group — all resolve to the same
    # PUT-family trio, so the union is exactly those three modules.
    idem = _ACCESS_SDK / "prisma_access" / "objects" / "extras" / "idempotency"
    assert idem.is_dir()
    assert (idem / "engine.py").exists() and (idem / "base.py").exists()
    assert _strategy_modules(idem) == {
        "fetch": {"list_scan"},
        "mutate": {"put_rmw"},
        "materialize": {"direct"},
    }


@pytest.mark.real_sdk
def test_browser_client_exposes_from_access_token(browser_pkg: Any) -> None:
    facade = importlib.import_module("prisma_browser.extras.facade")
    assert callable(getattr(facade.Client, "from_access_token", None))


@pytest.mark.real_sdk
def test_access_client_exposes_from_access_token(access_pkg: Any) -> None:
    assert callable(getattr(access_pkg.Client, "from_access_token", None))
