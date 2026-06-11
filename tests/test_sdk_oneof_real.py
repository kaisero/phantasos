"""Gated real-SDK test: oneOf discriminator dispatch picks the right variant.

Requires the sibling ../prisma-browser-sdk to be built (with the default
useOneOfDiscriminatorLookup=true). Locks in the 2026-06-11 fix for every
ApplicationItem deserializing as CustomApplication (trial-deser first-match
+ LenientStrEnum interaction).
"""

import sys
from pathlib import Path

import pytest

REAL_SDK = Path(__file__).parent.parent.parent / "prisma-browser-sdk"

_BASE = {
    "id": "app-0001",
    "name": "phx-test-app",
    "metadata": {
        "createdTime": "2026-01-01T00:00:00Z",
        "lastUpdatedTime": "2026-01-01T00:00:00Z",
    },
    "urls": ["*.example.com"],
}


@pytest.fixture
def application_item():
    if not REAL_SDK.exists():
        pytest.skip("prisma-browser-sdk not built")
    sys.path.insert(0, str(REAL_SDK))
    try:
        try:
            from prisma_browser.models.application_item import ApplicationItem
        except ImportError as exc:
            pytest.skip(f"prisma-browser-sdk runtime deps unavailable: {exc}")
        yield ApplicationItem
    finally:
        sys.path.remove(str(REAL_SDK))


@pytest.mark.parametrize(
    ("type_value", "expected_class"),
    [
        ("catalog", "CatalogApplication"),
        ("custom", "CustomApplication"),
        ("private", "PrivateApplication"),
        ("non-web", "NonWebApplication"),
    ],
)
def test_discriminator_picks_correct_variant(
    application_item, type_value, expected_class
):
    item = application_item.from_dict({**_BASE, "type": type_value})
    assert type(item.actual_instance).__name__ == expected_class


def test_catalog_fields_are_typed_not_demoted(application_item):
    item = application_item.from_dict(
        {**_BASE, "type": "catalog", "catalog_name": "ssl"}
    )
    inst = item.actual_instance
    assert inst.catalog_name == "ssl"
    assert "catalog_name" not in inst.additional_properties
