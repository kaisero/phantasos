from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.browser_brand import BrowserBrand
from ..types import UNSET, Unset

T = TypeVar("T", bound="BrowserBrandDetails")


@_attrs_define
class BrowserBrandDetails:
    """
    Attributes:
        brand (BrowserBrand): Browser brand
        min_version (str | Unset):
    """

    brand: BrowserBrand
    min_version: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        brand = self.brand.value

        min_version = self.min_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "brand": brand,
            }
        )
        if min_version is not UNSET:
            field_dict["minVersion"] = min_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        brand = BrowserBrand(d.pop("brand"))

        min_version = d.pop("minVersion", UNSET)

        browser_brand_details = cls(
            brand=brand,
            min_version=min_version,
        )

        browser_brand_details.additional_properties = d
        return browser_brand_details

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
