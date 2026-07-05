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


def _overrides() -> dict[str, OperationOverride]:
    """The product's real ``sdk.yml`` operations: block (B1) — NOT ``{}``."""
    from phantasos.productconfig import load_product

    return load_product("prisma-browser").config.operations


def test_object_granularity_and_multibinding(real_sdk: Path) -> None:
    inv = introspect("prisma_browser", real_sdk)
    overrides = _overrides()
    views = {
        v.attr: v
        for v in build_wrapper_context(
            inv, overrides, _discover_resources(real_sdk / "prisma_browser")
        )
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


def test_paramview_from_live_types(real_sdk: Path) -> None:
    """ParamView annotations come from LIVE introspected types, not ParamInfo repr."""
    inv = introspect("prisma_browser", real_sdk)
    views = {
        v.attr: v
        for v in build_wrapper_context(
            inv, _overrides(), _discover_resources(real_sdk / "prisma_browser")
        )
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


def test_none_classified_without_crud_anchor_fails(real_sdk: Path) -> None:
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


def _discover(sdk: Path) -> list[dict[str, str]]:
    from phantasos.generator.sdk.render import _discover_resources

    return _discover_resources(sdk / "prisma_browser")


def test_reference_examples_emitted_into_docstrings(real_sdk: Path) -> None:
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.productconfig import DocsConfig

    inv = introspect("prisma_browser", real_sdk)
    docs = DocsConfig(showcase_resource="application")
    objects = build_wrapper_context(inv, _overrides(), _discover(real_sdk), docs=docs)

    rule = next(o for o in objects if o.classname == "AccessAndDataRuleResource")
    create = next(m for m in rule.methods if m.name == "create")
    update = next(m for m in rule.methods if m.name == "update")
    get = next(m for m in rule.methods if m.name == "get")

    # create-style body -> synthesized example with the client path + body model
    assert "**Example:**" in create.docstring
    assert "client.access_and_data_rule.create(" in create.docstring
    assert "body=CreateAccessAndDataRuleRequest(" in create.docstring
    # path-only op -> client-path call with required id. Assert on substrings,
    # NOT an exact multi-line literal: `assemble_reference_docstring` re-indents
    # every continuation line by 8 spaces (so the call sits at 8, `id=` at 12),
    # and that indentation is an implementation detail of the assembler.
    assert "client.access_and_data_rule.get(" in get.docstring
    assert 'id="<id>"' in get.docstring
    # plain all-optional PATCH body -> nav line + empty body + optionality hint (D2)
    assert "**Example:**" in update.docstring
    assert "client.access_and_data_rule.update(" in update.docstring
    assert "# all fields optional" in update.docstring


def test_no_examples_when_docs_disabled(real_sdk: Path) -> None:
    # D5 inverse: docs=None -> one-line docstrings, no example block leaks in.
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.generator.sdk.wrapper import build_wrapper_context

    inv = introspect("prisma_browser", real_sdk)
    objects = build_wrapper_context(inv, _overrides(), _discover(real_sdk))  # no docs=
    for obj in objects:
        for m in obj.methods:
            assert "**Example:**" not in m.docstring
            assert "\n" not in m.docstring  # stays one line


def test_showcase_reference_honors_variant(real_sdk: Path) -> None:
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.productconfig import DocsConfig

    inv = introspect("prisma_browser", real_sdk)
    # application.create has a oneOf body. Use a NON-default variant so the test
    # actually proves variant threading: `CustomApplicationInput` is the FIRST
    # (default) variant, so asserting it would pass even if the variant arg were
    # dropped. `PrivateApplicationInput` is only emitted when the variant is honored.
    docs = DocsConfig(
        showcase_resource="application",
        showcase_variant="PrivateApplicationInput",
    )
    objects = build_wrapper_context(inv, _overrides(), _discover(real_sdk), docs=docs)
    app = next(o for o in objects if o.classname == "ApplicationResource")
    create = next(m for m in app.methods if m.name == "create")
    assert "PrivateApplicationInput(" in create.docstring
    assert "CustomApplicationInput(" not in create.docstring  # default did NOT win


def test_discriminated_patch_update_still_shows_example(real_sdk: Path) -> None:
    # Refined D2/D3: an all-optional PATCH is suppressed, BUT a oneOf PATCH whose
    # variant has a required discriminator synthesizes a NON-empty body, so it is
    # NOT suppressed. `application.update` (oneOf PatchAppInput) is the real case.
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.productconfig import DocsConfig

    inv = introspect("prisma_browser", real_sdk)
    objects = build_wrapper_context(
        inv,
        _overrides(),
        _discover(real_sdk),
        docs=DocsConfig(showcase_resource="application"),
    )
    app = next(o for o in objects if o.classname == "ApplicationResource")
    update = next(m for m in app.methods if m.name == "update")
    assert "**Example:**" in update.docstring  # NOT suppressed
    assert "client.application.update(" in update.docstring
    assert "body=" in update.docstring  # carries the discriminated variant


def test_showcase_override_used_verbatim_even_for_update(real_sdk: Path) -> None:
    from phantasos.generator.opmodel.introspect import introspect
    from phantasos.generator.sdk.wrapper import build_wrapper_context
    from phantasos.productconfig import DocsConfig, DocsExamples

    inv = introspect("prisma_browser", real_sdk)
    docs = DocsConfig(
        showcase_resource="access_and_data_rule",
        examples=DocsExamples(
            update='updated = client.access_and_data_rule.update(id="abc")'
        ),
    )
    objects = build_wrapper_context(inv, _overrides(), _discover(real_sdk), docs=docs)
    rule = next(o for o in objects if o.classname == "AccessAndDataRuleResource")
    update = next(m for m in rule.methods if m.name == "update")
    # D6: an authored override is shown even though synthesized update bodies are
    # suppressed.
    assert "**Example:**" in update.docstring
    assert 'updated = client.access_and_data_rule.update(id="abc")' in update.docstring
