from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MacOSVersion")


@_attrs_define
class MacOSVersion:
    """
    Attributes:
        enabled (bool):
        major (str):
        min_minor_version (str | Unset):
    """

    enabled: bool
    major: str
    min_minor_version: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        major = self.major

        min_minor_version = self.min_minor_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
                "major": major,
            }
        )
        if min_minor_version is not UNSET:
            field_dict["minMinorVersion"] = min_minor_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        major = d.pop("major")

        min_minor_version = d.pop("minMinorVersion", UNSET)

        mac_os_version = cls(
            enabled=enabled,
            major=major,
            min_minor_version=min_minor_version,
        )

        mac_os_version.additional_properties = d
        return mac_os_version

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
