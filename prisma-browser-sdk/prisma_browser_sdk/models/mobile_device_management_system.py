from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.mobile_device_management_system_name import MobileDeviceManagementSystemName
from ..types import UNSET, Unset

T = TypeVar("T", bound="MobileDeviceManagementSystem")


@_attrs_define
class MobileDeviceManagementSystem:
    """
    Attributes:
        name (MobileDeviceManagementSystemName):
        configuration_value (str | Unset):
    """

    name: MobileDeviceManagementSystemName
    configuration_value: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name.value

        configuration_value = self.configuration_value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if configuration_value is not UNSET:
            field_dict["configurationValue"] = configuration_value

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = MobileDeviceManagementSystemName(d.pop("name"))

        configuration_value = d.pop("configurationValue", UNSET)

        mobile_device_management_system = cls(
            name=name,
            configuration_value=configuration_value,
        )

        mobile_device_management_system.additional_properties = d
        return mobile_device_management_system

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
