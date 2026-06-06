from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.device_management_system_input import DeviceManagementSystemInput


T = TypeVar("T", bound="AttributeObjectDeviceManagement")


@_attrs_define
class AttributeObjectDeviceManagement:
    """Check if the device is managed by specific device management systems (e.g., Microsoft Intune, Jamf, Active
    Directory)

        Attributes:
            enabled (bool):
            negate (bool | Unset):  Default: False.
            systems (list[DeviceManagementSystemInput] | Unset): Device management system configurations
    """

    enabled: bool
    negate: bool | Unset = False
    systems: list[DeviceManagementSystemInput] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

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
        if negate is not UNSET:
            field_dict["negate"] = negate
        if systems is not UNSET:
            field_dict["systems"] = systems

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.device_management_system_input import DeviceManagementSystemInput

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _systems = d.pop("systems", UNSET)
        systems: list[DeviceManagementSystemInput] | Unset = UNSET
        if _systems is not UNSET:
            systems = []
            for systems_item_data in _systems:
                systems_item = DeviceManagementSystemInput.from_dict(systems_item_data)

                systems.append(systems_item)

        attribute_object_device_management = cls(
            enabled=enabled,
            negate=negate,
            systems=systems,
        )

        attribute_object_device_management.additional_properties = d
        return attribute_object_device_management

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
