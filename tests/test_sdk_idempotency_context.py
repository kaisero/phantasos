"""Baking the per-resource `_idempotency` metadata into the wrapper context.

Ring-3 real-artifact tests: they build the wrapper context against the locally
built SDKs (a sibling of the repo — ``../prisma-access-sdk`` for the federated
``prisma_access.objects`` sub-package, ``../prisma-browser-sdk`` for the
single-spec browser SDK) and assert the auto-selected strategy trio, the baked
metadata literal, the referenced-strategies union, and the seven build gates.

They skip (never fail) when a needed SDK is not built, so a fresh checkout and
the SDK-less CI ``tests`` job stay quiet; the ``smoke`` session builds them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from phantasos.config import IdempotencyConfig
from phantasos.generator.opmodel import introspect
from phantasos.generator.sdk.idempotency import referenced_strategies
from phantasos.generator.sdk.render import _discover_resources
from phantasos.generator.sdk.wrapper import ObjectView, build_wrapper_context

_REPO_PARENT = Path(__file__).resolve().parent.parent.parent
_ACCESS_SDK = _REPO_PARENT / "prisma-access-sdk"
_BROWSER_SDK = _REPO_PARENT / "prisma-browser-sdk"


@pytest.fixture
def access_sdk() -> Path:
    """Distribution root of the built federated prisma-access SDK."""
    if not (_ACCESS_SDK / "prisma_access" / "objects").exists():
        pytest.skip("prisma-access-sdk not built (run: nox -s smoke)")
    return _ACCESS_SDK


@pytest.fixture
def browser_sdk() -> Path:
    """Distribution root of the built single-spec prisma-browser SDK."""
    if not (_BROWSER_SDK / "prisma_browser").exists():
        pytest.skip("prisma-browser-sdk not built (run: nox -s smoke)")
    return _BROWSER_SDK


def _browser_overrides() -> dict[str, Any]:
    """The prisma-browser product's real ``sdk.yml`` operations: block.

    The single-spec browser SDK has None-classified position-reorder ops that
    fail ``build_wrapper_context`` without the product's overrides, so we pass
    the real block (mirrors ``test_sdk_wrapper.py``).
    """
    from phantasos.productconfig import load_product

    return load_product("prisma-browser").config.operations


def _access_views(dist_root: Path, cfg: IdempotencyConfig) -> dict[str, ObjectView]:
    inv = introspect("prisma_access.objects", dist_root)
    objects = build_wrapper_context(
        inv,
        {},
        _discover_resources(dist_root / "prisma_access" / "objects"),
        idempotency=cfg,
        dist_root=dist_root,
        has_pagination=True,
    )
    return {o.attr: o for o in objects}


def _browser_views(dist_root: Path, cfg: IdempotencyConfig) -> dict[str, ObjectView]:
    inv = introspect("prisma_browser", dist_root)
    objects = build_wrapper_context(
        inv,
        _browser_overrides(),
        _discover_resources(dist_root / "prisma_browser"),
        idempotency=cfg,
        dist_root=dist_root,
        has_pagination=True,
    )
    return {o.attr: o for o in objects}


def test_put_object_bakes_list_scan_put_rmw_direct(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
            "resources": {"address": {}},
        }
    )
    v = _access_views(access_sdk, cfg)["address"]
    assert v.sync is True
    lit = v.idempotency_literal
    # String values mirror `_bindings_literal`'s ``repr`` render (single-quoted);
    # ruff normalizes quotes when the emitted file is formatted.
    assert "\"fetch\": 'list_scan'" in lit
    assert "\"mutate\": 'put_rmw'" in lit
    assert "\"materialize\": 'direct'" in lit
    assert "\"update\": {'verb': 'replace'}" in lit
    assert "\"identity\": ['name']" in lit
    assert "'folder'" in lit and "'snippet'" in lit  # scope trio
    assert '"models": {"create": Addresses' in lit  # bare identifier, not a string
    assert ("prisma_access.objects.models.addresses", "Addresses") in v.imports


def test_patch_object_bakes_patch_minimal_get_after_write(browser_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate(
        {"defaults": {"read_only": ["id"]}, "resources": {"application_group": {}}}
    )
    v = _browser_views(browser_sdk, cfg)["application_group"]
    lit = v.idempotency_literal
    assert "\"fetch\": 'list_scan'" in lit  # no proven name filter -> default
    assert "\"mutate\": 'patch_minimal'" in lit
    assert "\"materialize\": 'get_after_write'" in lit
    assert "\"update\": {'verb': 'update'}" in lit


def test_referenced_strategies_returns_per_family_union(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
            "resources": {"address": {}, "tag": {}},
        }
    )
    objects = list(_access_views(access_sdk, cfg).values())
    ref = referenced_strategies(objects)
    assert ref == {
        "fetch": {"list_scan"},
        "mutate": {"put_rmw"},
        "materialize": {"direct"},
    }


def test_unknown_resource_key_gate(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate({"resources": {"nonexistent_obj": {}}})
    with pytest.raises(ValueError, match="nonexistent_obj"):
        _access_views(access_sdk, cfg)


def test_unresolvable_identity_gate(access_sdk: Path) -> None:
    # quarantined_device's create model has no `name` wire key and no annotation,
    # so without `sync: false` (or an explicit identity) it must fail loud.
    cfg = IdempotencyConfig.model_validate({"resources": {"quarantined_device": {}}})
    with pytest.raises(ValueError, match=r"quarantined_device.*identity"):
        _access_views(access_sdk, cfg)


def test_list_filter_without_query_param_gate(access_sdk: Path) -> None:
    # `description` is not a list query param on address, so a list_filter fetch
    # keyed on it must fail loud.
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
            "resources": {
                "address": {"fetch": "list_filter", "identity": ["description"]}
            },
        }
    )
    with pytest.raises(ValueError, match="list_filter"):
        _access_views(access_sdk, cfg)


def test_pagination_gate_when_no_component(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": {"scope": {"fields": ["folder", "snippet", "device"]}},
            "resources": {"address": {}},
        }
    )
    inv = introspect("prisma_access.objects", access_sdk)
    with pytest.raises(ValueError, match="pagination"):
        build_wrapper_context(
            inv,
            {},
            _discover_resources(access_sdk / "prisma_access" / "objects"),
            idempotency=cfg,
            dist_root=access_sdk,
            has_pagination=False,
        )


def test_singleton_sanity_gate(access_sdk: Path) -> None:
    # address has a create binding — declaring it singleton must fail.
    cfg = IdempotencyConfig.model_validate(
        {"resources": {"address": {"singleton": True}}}
    )
    with pytest.raises(ValueError, match="singleton"):
        _access_views(access_sdk, cfg)


def test_sync_false_keeps_object_off(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate(
        {"resources": {"quarantined_device": {"sync": False}}}
    )
    v = _access_views(access_sdk, cfg)["quarantined_device"]
    assert v.sync is False
    assert v.idempotency_literal == "{}"


def test_no_idempotency_leaves_every_object_off(access_sdk: Path) -> None:
    # Additive/opt-in exit check: idempotency=None -> sync False everywhere,
    # literal untouched, referenced_strategies empty.
    inv = introspect("prisma_access.objects", access_sdk)
    objects = build_wrapper_context(
        inv,
        {},
        _discover_resources(access_sdk / "prisma_access" / "objects"),
    )
    assert all(o.sync is False for o in objects)
    assert all(o.idempotency_literal == "{}" for o in objects)
    assert referenced_strategies(objects) == {
        "fetch": set(),
        "mutate": set(),
        "materialize": set(),
    }
