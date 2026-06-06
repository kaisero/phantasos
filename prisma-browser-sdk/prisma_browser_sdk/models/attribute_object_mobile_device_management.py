from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.mobile_device_management_system import MobileDeviceManagementSystem


T = TypeVar("T", bound="AttributeObjectMobileDeviceManagement")


@_attrs_define
class AttributeObjectMobileDeviceManagement:
    """Check if the mobile device is managed by specific mobile device management systems

    Attributes:
        enabled (bool):
        systems (list[MobileDeviceManagementSystem] | Unset): Mobile device management system configurations
    """

    enabled: bool
    systems: list[MobileDeviceManagementSystem] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        systems: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.systems, Unset):
            systems = []
            for systems_item_data in self.systems:
                systems_item = systems_item_data.to_dict()
                systems.append(systems_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if systems is not UNSET:
            field_dict["systems"] = systems

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.mobile_device_management_system import MobileDeviceManagementSystem

        d = dict(src_dict)
        enabled = d.pop("enabled")

        _systems = d.pop("systems", UNSET)
        systems: list[MobileDeviceManagementSystem] | Unset = UNSET
        if _systems is not UNSET:
            systems = []
            for systems_item_data in _systems:
                systems_item = MobileDeviceManagementSystem.from_dict(systems_item_data)

                systems.append(systems_item)

        attribute_object_mobile_device_management = cls(
            enabled=enabled,
            systems=systems,
        )

        attribute_object_mobile_device_management.additional_properties = d
        return attribute_object_mobile_device_management

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
