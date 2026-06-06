from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.browser_brand_details import BrowserBrandDetails


T = TypeVar("T", bound="AttributeObjectBrowserBrand")


@_attrs_define
class AttributeObjectBrowserBrand:
    """Check if the device has specific browser brands and versions installed

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        brands (list[BrowserBrandDetails] | Unset): Browser brand and version requirements
    """

    enabled: bool
    negate: bool | Unset = False
    brands: list[BrowserBrandDetails] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        brands: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.brands, Unset):
            brands = []
            for brands_item_data in self.brands:
                brands_item = brands_item_data.to_dict()
                brands.append(brands_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if brands is not UNSET:
            field_dict["brands"] = brands

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.browser_brand_details import BrowserBrandDetails

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _brands = d.pop("brands", UNSET)
        brands: list[BrowserBrandDetails] | Unset = UNSET
        if _brands is not UNSET:
            brands = []
            for brands_item_data in _brands:
                brands_item = BrowserBrandDetails.from_dict(brands_item_data)

                brands.append(brands_item)

        attribute_object_browser_brand = cls(
            enabled=enabled,
            negate=negate,
            brands=brands,
        )

        attribute_object_browser_brand.additional_properties = d
        return attribute_object_browser_brand

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
