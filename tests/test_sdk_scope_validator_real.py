"""Gated real-SDK test: the client-side scope mutual-exclusion validator.

Requires the sibling ../prisma-access-sdk to be built (``phantasos sdk build
prisma-access``). Proves against the REAL generated ``Addresses`` model — SCM's
one-schema-for-request-and-response object — that:

* a user-authored mutation body with ZERO scope containers is rejected at
  construction (the one shape a server never produces; UX / defense-in-depth);
* a server echo (a payload carrying the readOnly ``id``) round-trips
  ``model_validate`` with zero OR two containers, and an id-LESS inherited
  listing item (SCM's ``predefined`` snippet objects carry no id and SEVERAL
  containers) round-trips too, so building/reading real objects never crashes.

SKIPS cleanly when the SDK is not built or its runtime deps are unavailable.
NOTHING here is mocked: it drives the real generated model class.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from phantasos.productconfig import load_product


@pytest.fixture
def addresses() -> Iterator[Any]:
    loaded = load_product("prisma-access")
    sdk = Path(loaded.output_dir)
    pkg = loaded.config.package
    if not (sdk / Path(*pkg.split("."))).joinpath("__init__.py").exists():
        pytest.skip("prisma-access SDK not built (run `phantasos sdk build prisma-access`)")
    sys.path.insert(0, str(sdk))
    try:
        try:
            from prisma_access.objects.models.addresses import Addresses
        except ImportError as exc:
            pytest.skip(f"prisma-access SDK runtime deps unavailable: {exc}")
        # Skip (never fail) when the on-disk SDK predates this patch pass — i.e. was
        # built before `patch_scope_validators` existed. `nox -s smoke` rebuilds it
        # (prisma-access is enrolled), which is where this ring actually asserts.
        if not hasattr(Addresses, "_phantasos_scope_exactly_one"):
            pytest.skip("prisma-access SDK predates the scope validator (rebuild: nox -s smoke)")
        yield Addresses
    finally:
        sys.path.remove(str(sdk))


def test_scope_validator_present_on_real_model(addresses: Any) -> None:
    assert hasattr(addresses, "_phantasos_scope_exactly_one")


def test_mutation_body_requires_a_container(addresses: Any) -> None:
    # exactly one container -> constructs
    assert addresses(name="phx-test", folder="Shared", ip_netmask="1.1.1.1/32")
    # zero containers (and no id) -> rejected: the one shape a server never
    # produces, i.e. the classic user mistake of omitting the container.
    with pytest.raises(ValidationError):
        addresses(name="phx-test", ip_netmask="1.1.1.1/32")
    # two containers -> tolerated: folder listings surface INHERITED objects
    # (e.g. SCM's `predefined` snippet) with several containers set and NO id,
    # so the guard cannot raise on multi-container payloads without breaking
    # reads. A genuine multi-container write is rejected by the server itself.
    both = addresses(
        name="phx-test",
        folder="Shared",
        snippet="s",
        ip_netmask="1.1.1.1/32",
    )
    assert both.folder == "Shared" and both.snippet == "s"


def test_server_echo_bypasses_scope_guard(addresses: Any) -> None:
    # A server echo carries the readOnly `id`; it may legitimately have zero OR
    # several containers and MUST round-trip model_validate without raising.
    echo_none = addresses.model_validate({"id": "12345678-1234-1234-1234-123456789abc", "name": "phx-test"})
    assert echo_none.id == "12345678-1234-1234-1234-123456789abc"
    echo_two = addresses.model_validate(
        {
            "id": "12345678-1234-1234-1234-123456789abc",
            "name": "phx-test",
            "folder": "Shared",
            "snippet": "s",
        }
    )
    assert echo_two.folder == "Shared" and echo_two.snippet == "s"


def test_id_less_inherited_listing_item_bypasses_scope_guard(addresses: Any) -> None:
    # Live-proven SCM shape (test_service_idempotency_round_trip found it): a
    # folder listing surfaces objects inherited from the `predefined` snippet
    # with NO id and BOTH folder and snippet set. Deserializing one must not
    # raise, or every list_scan over such a folder crashes.
    item = addresses.model_validate({"name": "service-http", "folder": "Shared", "snippet": "predefined"})
    assert item.id is None
    assert item.folder == "Shared" and item.snippet == "predefined"


@pytest.fixture
def auto_tag_actions() -> Iterator[Any]:
    """The one id-LESS scoped model (SCM keys it by ``name``, not ``id``).

    Its server List/echo payloads carry NO ``id``, so the server-echo guard
    cannot distinguish an echo from a mutation body — the validator must NOT be
    emitted for it, else 0/≥2-container echoes would false-positive.
    """
    loaded = load_product("prisma-access")
    sdk = Path(loaded.output_dir)
    pkg = loaded.config.package
    if not (sdk / Path(*pkg.split("."))).joinpath("__init__.py").exists():
        pytest.skip("prisma-access SDK not built (run `phantasos sdk build prisma-access`)")
    sys.path.insert(0, str(sdk))
    try:
        try:
            from prisma_access.objects.models.auto_tag_actions import AutoTagActions
        except ImportError as exc:
            pytest.skip(f"prisma-access SDK runtime deps unavailable: {exc}")
        fields = AutoTagActions.model_fields
        if "folder" not in fields or "id" in fields:
            pytest.skip("auto_tag_actions is not the expected id-less scoped model")
        # Skip (never fail) when the on-disk SDK predates the id-guard fix — i.e.
        # was built while the id-less validator was still emitted. `nox -s smoke`
        # rebuilds it, which is where this ring actually asserts.
        if hasattr(AutoTagActions, "_phantasos_scope_exactly_one"):
            pytest.skip("prisma-access SDK predates the id-less scope-guard fix (rebuild: nox -s smoke)")
        yield AutoTagActions
    finally:
        sys.path.remove(str(sdk))


def test_id_less_scoped_model_has_no_validator(auto_tag_actions: Any) -> None:
    # The id-less scoped model must NOT carry the unconditional scope validator.
    assert not hasattr(auto_tag_actions, "_phantasos_scope_exactly_one")


def test_id_less_scoped_model_accepts_zero_or_two_containers(
    auto_tag_actions: Any,
) -> None:
    # Without the validator, an id-less echo with 0 OR 2 containers must NOT raise
    # (the server enforces the scope rule with a 400 on a bad body instead).
    # `name`/`filter` are the schema-required fields, unrelated to the scope group.
    zero = auto_tag_actions.model_validate({"name": "phx-test", "filter": "tag1"})
    assert zero.name == "phx-test"
    two = auto_tag_actions.model_validate({"name": "phx-test", "filter": "tag1", "folder": "Shared", "snippet": "s"})
    assert two.folder == "Shared" and two.snippet == "s"
