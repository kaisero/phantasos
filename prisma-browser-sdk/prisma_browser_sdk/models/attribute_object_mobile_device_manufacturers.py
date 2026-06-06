from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.mobile_manufacturer import MobileManufacturer
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttributeObjectMobileDeviceManufacturers")


@_attrs_define
class AttributeObjectMobileDeviceManufacturers:
    """Check if the mobile device is from specific manufacturers (e.g., Apple, Samsung)

    Attributes:
        enabled (bool):
        vendors (list[MobileManufacturer] | Unset): List of mobile device manufacturers to check for
    """

    enabled: bool
    vendors: list[MobileManufacturer] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        vendors: list[str] | Unset = UNSET
        if not isinstance(self.vendors, Unset):
            vendors = []
            for vendors_item_data in self.vendors:
                vendors_item = vendors_item_data.value
                vendors.append(vendors_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if vendors is not UNSET:
            field_dict["vendors"] = vendors

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        _vendors = d.pop("vendors", UNSET)
        vendors: list[MobileManufacturer] | Unset = UNSET
        if _vendors is not UNSET:
            vendors = []
            for vendors_item_data in _vendors:
                vendors_item = MobileManufacturer(vendors_item_data)

                vendors.append(vendors_item)

        attribute_object_mobile_device_manufacturers = cls(
            enabled=enabled,
            vendors=vendors,
        )

        attribute_object_mobile_device_manufacturers.additional_properties = d
        return attribute_object_mobile_device_manufacturers

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
