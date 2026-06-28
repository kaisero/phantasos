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
from phantasos.generator.cli.ir import CliIR, Command

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
    # naive flat models merge carries both subs' body models (B2 namespaces collisions).
    assert "WidgetInput" in ir.models and "GadgetInput" in ir.models


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
