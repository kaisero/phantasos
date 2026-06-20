"""Object-granular wrapper render context (Task 3.1).

Runs against the locally-built prisma-browser SDK at ``../prisma-browser-sdk``
(skips when absent). The wrapper context decides which typed
``client.<object>.<verb>(...)`` wrappers to emit, with multi-binding dispatch
metadata — it is grouped by the CLASSIFIED OBJECT, not ``op.resource``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phantasos.config import OperationOverride
from phantasos.generator.opmodel import introspect
from phantasos.generator.sdk.render import _discover_resources
from phantasos.generator.sdk.wrapper import build_wrapper_context

SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"
PKG = SDK / "prisma_browser"


def _overrides() -> dict[str, OperationOverride]:
    """The product's real ``sdk.yml`` operations: block (B1) — NOT ``{}``."""
    from phantasos.productconfig import load_product

    return load_product("prisma-browser").config.operations


@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_object_granularity_and_multibinding() -> None:
    inv = introspect("prisma_browser", SDK)
    overrides = _overrides()
    views = {
        v.attr: v
        for v in build_wrapper_context(inv, overrides, _discover_resources(PKG))
    }
    # RA: the access_and_data_policy api class backs THREE object wrappers.
    assert {
        "access_and_data_rule",
        "access_and_data_section",
        "access_and_data_policy",
    } <= set(views)
    # RB: application has clean CRUD; .get / .list / .delete each collapse two
    # raw ops into ONE method with two bindings (by-id + by-type-and-id).
    app = views["application"]
    m = {x.name: x for x in app.methods}
    # PATCH classifies to the canonical `update` verb (sub_verb `patch` only
    # disambiguates `show` -> get/list).
    assert {"create", "get", "list", "delete", "update"} <= set(m)
    assert m["get"].bindings and len(m["get"].bindings) == 2  # by-id + by-type-and-id
    assert len(m["list"].bindings) == 2 and m["list"].is_list
    assert len(m["delete"].bindings) == 2
    assert "bulk_create" in m  # bulk_create_applications -> application.bulk_create
    # RD: PUT update_* -> replace, and verb-phrase actions attach to the EXISTING
    # CRUD object — no junk objects spawned.
    assert "replace" in {x.name for x in views["device_group"].methods}  # PUT
    assert "suspend" in {x.name for x in views["device"].methods}  # suspend_devices
    assert "revoke" in {x.name for x in views["user_request"].methods}
    # B1 overrides: position-reorder ops attach to the EXISTING *-section objects.
    sec = {x.name for x in views["security_section"].methods}
    assert {"reorder", "reorder_patch", "replace"} <= sec
    # configuration: a NEW single-method object created by the override.
    assert "publish" in {x.name for x in views["configuration"].methods}
    # NO junk objects.
    for junk in (
        "update_device_group",
        "suspend_device",
        "security_position",
        "access_and_data_position",
    ):
        assert junk not in views


@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_paramview_from_live_types() -> None:
    """ParamView annotations come from LIVE introspected types, not ParamInfo repr."""
    inv = introspect("prisma_browser", SDK)
    views = {
        v.attr: v
        for v in build_wrapper_context(inv, _overrides(), _discover_resources(PKG))
    }
    dg = views["device_group"]
    listm = next(x for x in dg.methods if x.name == "list")
    plat = next(p for p in listm.params if p.name == "device_group_platform")
    # Real enum type -> render expr + import (module, qualname), not "<enum '...'>".
    assert plat.py_annotation == "DeviceGroupPlatform | None"
    assert plat.import_from == (
        "models.device_group_platform",
        "DeviceGroupPlatform",
    )
    assert "<enum" not in plat.py_annotation
    # The body param is renamed to `body` but keeps its raw_name.
    replace = next(x for x in dg.methods if x.name == "replace")
    assert replace.body is not None
    assert replace.body.name == "body"
    assert replace.body.raw_name == "device_group_request"


@pytest.mark.skipif(not SDK.exists(), reason="prisma-browser SDK not built")
def test_none_classified_without_crud_anchor_fails() -> None:
    from phantasos.generator.opmodel.inventory import (
        OperationInfo,
        OperationInventory,
    )

    inv = OperationInventory(
        sdk_package="p",
        sdk_version="0",
        operations=[
            OperationInfo(resource="ops", method="publish_draft_configuration")
        ],
    )
    with pytest.raises(ValueError, match="maps to no CRUD object"):
        build_wrapper_context(
            inv, {}, [{"attr": "ops", "module": "ops_api", "cls": "OpsApi"}]
        )


def test_collision_fails() -> None:
    from phantasos.generator.sdk.wrapper import (
        MethodView,
        ObjectView,
        _gate_collisions,
    )

    ov = ObjectView(
        attr="x",
        classname="X",
        api_cls="A",
        api_module="a",
        api_attr="xs",
        methods=[
            MethodView("get", "show", [], None, "I", None, [], False, False),
            MethodView("get", "show", [], None, "I", None, [], False, False),
        ],
        imports=set(),
    )
    with pytest.raises(ValueError, match="method name collision"):
        _gate_collisions([ov])
