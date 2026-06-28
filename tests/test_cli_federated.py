"""Federation-aware host build: loop `_SUBPACKAGES`, merge into one CliIR.

Builds the IR through the FEDERATED path (the `fedsdk` fixture: two subs alpha/beta)
and the single-spec path (`fakesdk`), asserting each command is stamped with its snake
slug only in the federated case, that the single-spec path is unchanged
(`subpackage is None`), and that a cross-sub OBJECT collision is rejected (S1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from phantasos.generator.cli.classify import build_ir, merge_federated_irs
from phantasos.generator.cli.cliconfig import CliConfig
from phantasos.generator.cli.ir import CliIR, Command, synth_skeleton

FEDSDK = Path(__file__).parent / "fixtures" / "fedsdk"
FAKESDK = Path(__file__).parent / "fixtures" / "fakesdk"


def test_federated_build_stamps_each_command_with_its_slug() -> None:
    ir, unmapped = build_ir("fedsdk", FEDSDK, CliConfig())
    assert ir.sdk_package == "fedsdk"
    # the composing Client lives on the top-level package, not a sub-facade.
    assert ir.facade_module == "fedsdk"
    by_object = {(c.object, c.verb): c.subpackage for c in ir.commands}
    # alpha's widget CRUD stamped "alpha"; beta's gadget CRUD stamped "beta".
    assert by_object[("widget", "create")] == "alpha"
    assert by_object[("widget", "show")] == "alpha"
    assert by_object[("gadget", "create")] == "beta"
    assert by_object[("gadget", "delete")] == "beta"
    # every command in a federated build carries a slug.
    assert all(c.subpackage in {"alpha", "beta"} for c in ir.commands)
    # beta's non-CRUD `compute` is unmapped (no request mapping), slug-prefixed.
    assert any(u.startswith("beta.") and "compute" in u for u in unmapped)
    # the federated merge slug-qualifies every registry key (B2).
    assert "alpha.WidgetInput" in ir.models and "beta.GadgetInput" in ir.models


def test_single_spec_build_leaves_subpackage_none() -> None:
    ir, _ = build_ir("fakesdk", FAKESDK, CliConfig())
    assert ir.commands  # the single-spec path still produces commands
    assert all(c.subpackage is None for c in ir.commands)
    # single-spec facade_module stays the per-package facade (path unchanged).
    assert ir.facade_module == "fakesdk.extras.facade"


def _stub_ir(object_name: str) -> CliIR:
    cmd = Command(
        verb="show",
        object=object_name,
        key=f"show:{object_name}",
        sdk_resource=object_name,
    )
    return CliIR(sdk_package="x", sdk_version="0", commands=[cmd])


def test_duplicate_object_across_subs_raises() -> None:
    subs: list[tuple[str, CliIR, list[str]]] = [
        ("alpha", _stub_ir("thing"), []),
        ("beta", _stub_ir("thing"), []),
    ]
    with pytest.raises(ValueError, match=r"thing.*alpha.*beta|thing"):
        merge_federated_irs("fed", "0.0.1", subs)


def test_federated_merge_namespaces_colliding_models() -> None:
    """Both subs define a `PageInfo` reachable from their body root (alpha:
    {cursor}, beta: {total}). The flat B1 merge kept ONE `PageInfo` (last-sub-wins),
    so alpha's `--page-info` flag resolved to beta's shape. B2 slug-qualifies keys
    AND rewrites refs, keeping both models distinct and each flag pointing home.
    """
    ir, _ = build_ir("fedsdk", FEDSDK, CliConfig())

    # both subs' PageInfo survive under distinct slug-qualified keys, un-overwritten.
    assert "alpha.PageInfo" in ir.models and "beta.PageInfo" in ir.models
    assert {mf.alias for mf in ir.models["alpha.PageInfo"].fields} == {"cursor"}
    assert {mf.alias for mf in ir.models["beta.PageInfo"].fields} == {"total"}
    # the bare colliding key is gone — every federated key is qualified.
    assert "PageInfo" not in ir.models

    # alpha's widget body flag points at ALPHA's qualified PageInfo (not beta's).
    create_widget = next(
        c for c in ir.commands if c.object == "widget" and c.verb == "create"
    )
    page_flag = next(f for f in create_widget.body_flags if f.param == "page_info")
    assert page_flag.model_ref == "alpha.PageInfo"

    # and the skeleton synthesizer resolves that ref to ALPHA's shape, not beta's.
    skel = synth_skeleton(ir.models, page_flag.model_ref, full=True)
    assert set(skel) == {"cursor"}


def test_single_spec_registry_keys_stay_bare() -> None:
    """Behavioral parity: the single-spec path runs no merge, so registry keys and
    body-flag `model_ref`s stay BARE (unqualified) — unchanged from before B2."""
    ir, _ = build_ir("fakesdk", FAKESDK, CliConfig())
    assert ir.models  # the single-spec build still produces a registry
    assert all("." not in key for key in ir.models)
    for cmd in ir.commands:
        for flag in cmd.body_flags:
            if flag.model_ref:
                assert "." not in flag.model_ref
