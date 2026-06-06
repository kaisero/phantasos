from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.management_system_type import ManagementSystemType
from ..types import UNSET, Unset

T = TypeVar("T", bound="DeviceManagementSystemInput")


@_attrs_define
class DeviceManagementSystemInput:
    """
    Attributes:
        name (ManagementSystemType): Device management system type
        domains (list[str] | Unset):
    """

    name: ManagementSystemType
    domains: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name.value

        domains: list[str] | Unset = UNSET
        if not isinstance(self.domains, Unset):
            domains = self.domains

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if domains is not UNSET:
            field_dict["domains"] = domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = ManagementSystemType(d.pop("name"))

        domains = cast(list[str], d.pop("domains", UNSET))

        device_management_system_input = cls(
            name=name,
            domains=domains,
        )

        device_management_system_input.additional_properties = d
        return device_management_system_input

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
