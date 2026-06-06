from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.selected_device_vendor import SelectedDeviceVendor


T = TypeVar("T", bound="AttributeObjectDeviceManufacturer")


@_attrs_define
class AttributeObjectDeviceManufacturer:
    """Check if the device is from specific manufacturers (e.g., Dell, HP, Lenovo)

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        selected_vendors (list[SelectedDeviceVendor] | Unset): List of device manufacturers with optional specific
            models to check for
    """

    enabled: bool
    negate: bool | Unset = False
    selected_vendors: list[SelectedDeviceVendor] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        selected_vendors: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.selected_vendors, Unset):
            selected_vendors = []
            for selected_vendors_item_data in self.selected_vendors:
                selected_vendors_item = selected_vendors_item_data.to_dict()
                selected_vendors.append(selected_vendors_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if selected_vendors is not UNSET:
            field_dict["selectedVendors"] = selected_vendors

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.selected_device_vendor import SelectedDeviceVendor

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _selected_vendors = d.pop("selectedVendors", UNSET)
        selected_vendors: list[SelectedDeviceVendor] | Unset = UNSET
        if _selected_vendors is not UNSET:
            selected_vendors = []
            for selected_vendors_item_data in _selected_vendors:
                selected_vendors_item = SelectedDeviceVendor.from_dict(selected_vendors_item_data)

                selected_vendors.append(selected_vendors_item)

        attribute_object_device_manufacturer = cls(
            enabled=enabled,
            negate=negate,
            selected_vendors=selected_vendors,
        )

        attribute_object_device_manufacturer.additional_properties = d
        return attribute_object_device_manufacturer

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
