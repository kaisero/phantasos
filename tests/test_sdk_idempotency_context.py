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


@pytest.fixture
def deployment_sdk() -> Path:
    """Distribution root of the built federated deployment_services sub-package."""
    if not (_ACCESS_SDK / "prisma_access" / "deployment_services").exists():
        pytest.skip("prisma-access-sdk not built (run: nox -s smoke)")
    return _ACCESS_SDK


def _deployment_views(dist_root: Path, cfg: IdempotencyConfig) -> dict[str, ObjectView]:
    sub = dist_root / "prisma_access" / "deployment_services"
    inv = introspect("prisma_access.deployment_services", dist_root)
    objects = build_wrapper_context(
        inv,
        {},
        _discover_resources(sub),
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
    # Package-relative (prefix stripped), matching wrapper param/return imports so
    # resources.py emits `from ..models.addresses import Addresses` correctly.
    assert ("models.addresses", "Addresses") in v.imports


def test_patch_object_bakes_patch_minimal_get_after_write(browser_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate({"defaults": {"read_only": ["id"]}, "resources": {"application_group": {}}})
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
            "resources": {"address": {"fetch": "list_filter", "identity": ["description"]}},
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
    cfg = IdempotencyConfig.model_validate({"resources": {"address": {"singleton": True}}})
    with pytest.raises(ValueError, match="singleton"):
        _access_views(access_sdk, cfg)


def test_singleton_bgp_routing_bakes_get_put_singleton_direct(
    deployment_sdk: Path,
) -> None:
    # bgp_routing is a true singleton (GET + PUT, no id): its update-on-drift must
    # auto-select the id-less `put_singleton` mutate, not `put_rmw` (which would
    # crash extracting an absent id). fetch is `get`; identity is empty.
    cfg = IdempotencyConfig.model_validate({"resources": {"bgp_routing": {"singleton": True, "identity": []}}})
    v = _deployment_views(deployment_sdk, cfg)["bgp_routing"]
    assert v.sync is True
    lit = v.idempotency_literal
    assert "\"fetch\": 'get'" in lit
    assert "\"mutate\": 'put_singleton'" in lit
    assert '"singleton": True' in lit
    assert "\"update\": {'verb': 'replace'}" in lit
    ref = referenced_strategies([v])
    assert ref["mutate"] == {"put_singleton"}


def test_sync_false_keeps_object_off(access_sdk: Path) -> None:
    cfg = IdempotencyConfig.model_validate({"resources": {"quarantined_device": {"sync": False}}})
    v = _access_views(access_sdk, cfg)["quarantined_device"]
    assert v.sync is False
    assert v.idempotency_literal == "{}"


def test_write_only_field_resolves_f6_gate(browser_sdk: Path) -> None:
    # F6: user_group's write models carry `userIds` (create) and `users`
    # (update), but the UserGroup read model echoes neither — managed fields
    # undetectable via GET. Declaring them under `write_only:` accepts the
    # resource (knowingly partial sync) and bakes them into the literal so the
    # engine subtracts them from the diff. Both undetectable fields must be
    # listed — an escape hatch that only covers one still trips the gate on the
    # other (see test_write_only_partial_declaration_still_fails_f6_gate).
    cfg = IdempotencyConfig.model_validate(
        {
            "resources": {
                "user_group": {
                    "identity": ["name"],
                    "write_only": ["userIds", "users"],
                }
            }
        }
    )
    v = _browser_views(browser_sdk, cfg)["user_group"]
    assert v.sync is True
    assert "'userIds'" in v.idempotency_literal
    assert "\"write_only\": ['userIds', 'users']" in v.idempotency_literal


def test_write_only_undeclared_field_fails_f6_gate(browser_sdk: Path) -> None:
    # Same resource WITHOUT `write_only:` must fail the F6 gate loud — the fields
    # stay managed, are absent from the read model, so drift on them is
    # undetectable. The message names them AND the two resolutions.
    cfg = IdempotencyConfig.model_validate({"resources": {"user_group": {"identity": ["name"]}}})
    with pytest.raises(ValueError, match=r"user_group.*undetectable.*write_only"):
        _browser_views(browser_sdk, cfg)


def test_write_only_partial_declaration_still_fails_f6_gate(browser_sdk: Path) -> None:
    # The escape hatch is per-field: declaring only ONE of two undetectable
    # managed fields still fails the gate on the remaining one, so nothing goes
    # undetected silently.
    cfg = IdempotencyConfig.model_validate(
        {"resources": {"user_group": {"identity": ["name"], "write_only": ["userIds"]}}}
    )
    with pytest.raises(ValueError, match=r"user_group.*users.*write_only"):
        _browser_views(browser_sdk, cfg)


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


# --- extra-required call params (`params` meta + gate #8) -------------------


def _product_sub_operations(slug: str) -> dict[str, Any]:
    """The prisma-access product's real per-subpackage ``operations:`` block."""
    from phantasos.productconfig import load_product

    return next(s.config.operations for s in load_product("prisma-access").subpackages if s.config.slug == slug)


def _sub_views(dist_root: Path, slug: str, cfg: IdempotencyConfig) -> dict[str, ObjectView]:
    inv = introspect(f"prisma_access.{slug}", dist_root)
    objects = build_wrapper_context(
        inv,
        _product_sub_operations(slug),
        _discover_resources(dist_root / "prisma_access" / slug),
        idempotency=cfg,
        dist_root=dist_root,
        has_pagination=True,
    )
    return {o.attr: o for o in objects}


def _sub_sdk(slug: str) -> Path:
    if not (_ACCESS_SDK / "prisma_access" / slug).exists():
        pytest.skip("prisma-access-sdk not built (run: nox -s smoke)")
    return _ACCESS_SDK


_SCOPE_TRIO = {"scope": {"fields": ["folder", "snippet", "device"]}}


def test_position_rule_bakes_params_meta_with_per_verb_threading() -> None:
    # nat_rule: `position` is a required pre/post query enum on list, create AND
    # replace (unique among the rules) — the producer must auto-derive the value
    # set + verbs from the bindings and take ONLY the default from config.
    dist = _sub_sdk("network_services")
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": _SCOPE_TRIO,
            "resources": {"nat_rule": {"params": {"position": {"default": "pre"}}}},
        }
    )
    v = _sub_views(dist, "network_services", cfg)["nat_rule"]
    assert v.sync is True
    meta = v._idempotency_meta  # type: ignore[attr-defined]
    assert meta["params"] == {
        "position": {
            "values": ["pre", "post"],
            "verbs": ["list", "create", "replace"],
            "default": "pre",
        }
    }
    lit = v.idempotency_literal
    assert "\"params\": {'position': {'values': ['pre', 'post'], " in lit


def test_list_only_position_bakes_list_verb_only() -> None:
    # mfa_server: the position param is a spec wart on its LIST op only (create
    # takes nothing) — verbs must be exactly ["list"], so the engine never
    # forwards position to create/replace.
    dist = _sub_sdk("identity_services")
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": _SCOPE_TRIO,
            "resources": {"mfa_server": {"params": {"position": {"default": "pre"}}}},
        }
    )
    v = _sub_views(dist, "identity_services", cfg)["mfa_server"]
    meta = v._idempotency_meta  # type: ignore[attr-defined]
    assert meta["params"]["position"]["verbs"] == ["list"]
    assert meta["params"]["position"]["values"] == ["pre", "post"]


def test_non_enum_required_param_trips_gate8() -> None:
    # ztna connector_scheduled_upgrade: create/replace require `oid` — a
    # free-form parent id, not an enum the engine can thread. Opting it in must
    # fail LOUD at build time (gate #8), replacing today's silent
    # "gates-green but undrivable" shape.
    dist = _sub_sdk("ztna_connector")
    cfg = IdempotencyConfig.model_validate({"resources": {"connector_scheduled_upgrade": {"identity": ["oid"]}}})
    with pytest.raises(ValueError, match=r"connector_scheduled_upgrade.*'oid'.*sync: false"):
        _sub_views(dist, "ztna_connector", cfg)


def test_plain_resource_bakes_no_params_key(access_sdk: Path) -> None:
    # Byte-identical guarantee: a resource with no extra-required param bakes
    # NO `params` key at all — neither in the meta nor in the emitted literal.
    cfg = IdempotencyConfig.model_validate({"defaults": _SCOPE_TRIO, "resources": {"address": {}}})
    v = _access_views(access_sdk, cfg)["address"]
    assert "params" not in v._idempotency_meta  # type: ignore[attr-defined]
    assert '"params"' not in v.idempotency_literal


def test_declared_param_unknown_to_surface_fails_loud(access_sdk: Path) -> None:
    # Config may only set the default of a DETECTED param — declaring one the
    # resource's ops never require is a config bug, named loud.
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": _SCOPE_TRIO,
            "resources": {"address": {"params": {"position": {"default": "pre"}}}},
        }
    )
    with pytest.raises(ValueError, match=r"address.*position"):
        _access_views(access_sdk, cfg)


def test_declared_default_outside_enum_fails_loud() -> None:
    dist = _sub_sdk("network_services")
    cfg = IdempotencyConfig.model_validate(
        {
            "defaults": _SCOPE_TRIO,
            "resources": {"nat_rule": {"params": {"position": {"default": "mid"}}}},
        }
    )
    with pytest.raises(ValueError, match=r"nat_rule.*mid"):
        _sub_views(dist, "network_services", cfg)


@pytest.fixture
def security_sdk() -> Path:
    """Distribution root of the built federated security_services sub-package."""
    if not (_ACCESS_SDK / "prisma_access" / "security_services").exists():
        pytest.skip("prisma-access-sdk not built (run: nox -s smoke)")
    return _ACCESS_SDK


def test_security_services_list_rules_rebound_and_shape_defects_stay_off(
    security_sdk: Path,
) -> None:
    # GET /security-rules carries the bare operationId `ListRules`; unlike its
    # api-class siblings (`CreateSecurityRules`, `GetSecurityRulesByID`, ...) it
    # names no object, so it classifies to a spurious read-only `rule` resource
    # instead of joining `security_rule`. The product's sdk.yml `operations:`
    # rebind must fold it back in — completing security_rule's surface
    # (create/delete/get/list/move/replace) and removing the `rule` wart.
    #
    # Pinned with the product's REAL per-sub config: security_rule stays a
    # documented skip — the ListRules rebind + the position engine solve its
    # surface and `position`, but its SecurityRules model uniquely declares the
    # scope fields REQUIRED, so a single-scope body won't construct (a separate
    # model-shape defect). ssl_decryption_setting / saas_tenant_restriction also
    # stay skips (gate #5 — list-envelope GET hides every managed write field).
    from phantasos.productconfig import load_product

    sub = next(s.config for s in load_product("prisma-access").subpackages if s.config.slug == "security_services")
    inv = introspect("prisma_access.security_services", security_sdk)
    objects = build_wrapper_context(
        inv,
        sub.operations,
        _discover_resources(security_sdk / "prisma_access" / "security_services"),
        idempotency=sub.idempotency,
        dist_root=security_sdk,
        has_pagination=True,
    )
    by_attr = {o.attr: o for o in objects}
    assert "rule" not in by_attr, "ListRules must rebind onto security_rule"
    sec = by_attr["security_rule"]
    assert sorted(m.name for m in sec.methods) == [
        "create",
        "delete",
        "get",
        "list",
        "move",
        "replace",
    ]
    assert sec.sync is False, (
        "security_rule stays OUT: the ListRules rebind + position engine make it "
        "CRUD-complete and position-threadable, but its SecurityRules model uniquely "
        "declares folder/snippet/device as REQUIRED (not Optional), so a single-scope "
        "body cannot be constructed client-side — a separate model-shape defect, not a "
        "position problem"
    )
    for attr in ("security_rule", "ssl_decryption_setting", "saas_tenant_restriction"):
        assert by_attr[attr].sync is False, f"{attr} must stay a documented skip"


def test_product_opts_in_the_position_rules_with_position_param() -> None:
    # The product's REAL sdk.yml opts six position-ordered rule resources
    # into sync, each declaring `params: {position: {default: pre}}`. The baked
    # meta must carry the auto-derived pre/post value set and the per-resource
    # requiring verbs: every rule needs position on list; all but mfa_server
    # (whose create takes nothing — the position is a spec wart on its list op)
    # need it on create; nat_rule uniquely also needs it on replace.
    from phantasos.productconfig import load_product

    expected_verbs = {
        "network_services": {
            "nat_rule": ["list", "create", "replace"],
            "qo_s_policy_rule": ["list", "create"],
        },
        "identity_services": {
            "authentication_rule": ["list", "create"],
            "mfa_server": ["list"],
        },
        "security_services": {
            "application_override_rule": ["list", "create"],
            "decryption_rule": ["list", "create"],
        },
    }
    subs = {s.config.slug: s.config for s in load_product("prisma-access").subpackages}
    for slug, rules in expected_verbs.items():
        dist = _sub_sdk(slug)
        cfg = subs[slug].idempotency
        assert cfg is not None
        views = _sub_views(dist, slug, cfg)
        for attr, verbs in rules.items():
            v = views[attr]
            assert v.sync is True, f"{slug}.{attr} must be opted in"
            meta = v._idempotency_meta  # type: ignore[attr-defined]
            assert meta["params"] == {
                "position": {
                    "values": ["pre", "post"],
                    "verbs": verbs,
                    "default": "pre",
                }
            }, f"{slug}.{attr}"
            lit = v.idempotency_literal
            assert "\"params\": {'position':" in lit, f"{slug}.{attr}"
