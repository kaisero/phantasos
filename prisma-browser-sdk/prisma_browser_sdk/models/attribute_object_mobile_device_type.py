from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.mobile_device_type import MobileDeviceType
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttributeObjectMobileDeviceType")


@_attrs_define
class AttributeObjectMobileDeviceType:
    """Check if the mobile device matches specific types (e.g., phone, tablet)

    Attributes:
        enabled (bool):
        types (list[MobileDeviceType] | Unset): List of mobile device types to check for
    """

    enabled: bool
    types: list[MobileDeviceType] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        types: list[str] | Unset = UNSET
        if not isinstance(self.types, Unset):
            types = []
            for types_item_data in self.types:
                types_item = types_item_data.value
                types.append(types_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if types is not UNSET:
            field_dict["types"] = types

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        _types = d.pop("types", UNSET)
        types: list[MobileDeviceType] | Unset = UNSET
        if _types is not UNSET:
            types = []
            for types_item_data in _types:
                types_item = MobileDeviceType(types_item_data)

                types.append(types_item)

        attribute_object_mobile_device_type = cls(
            enabled=enabled,
            types=types,
        )

        attribute_object_mobile_device_type.additional_properties = d
        return attribute_object_mobile_device_type

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
