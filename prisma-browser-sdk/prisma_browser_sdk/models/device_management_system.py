from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.device_management_system_system import DeviceManagementSystemSystem
from ..types import UNSET, Unset

T = TypeVar("T", bound="DeviceManagementSystem")


@_attrs_define
class DeviceManagementSystem:
    """
    Attributes:
        system (DeviceManagementSystemSystem | Unset):
        details (str | Unset):
    """

    system: DeviceManagementSystemSystem | Unset = UNSET
    details: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        system: str | Unset = UNSET
        if not isinstance(self.system, Unset):
            system = self.system.value

        details = self.details

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if system is not UNSET:
            field_dict["system"] = system
        if details is not UNSET:
            field_dict["details"] = details

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _system = d.pop("system", UNSET)
        system: DeviceManagementSystemSystem | Unset
        if isinstance(_system, Unset):
            system = UNSET
        else:
            system = DeviceManagementSystemSystem(_system)

        details = d.pop("details", UNSET)

        device_management_system = cls(
            system=system,
            details=details,
        )

        device_management_system.additional_properties = d
        return device_management_system

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
