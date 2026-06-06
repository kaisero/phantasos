from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.windows_edition import WindowsEdition
from ..types import UNSET, Unset

T = TypeVar("T", bound="WindowsVersion")


@_attrs_define
class WindowsVersion:
    """
    Attributes:
        enabled (bool):
        major (str):
        min_build_number (str | Unset):
        editions (list[WindowsEdition] | Unset):
    """

    enabled: bool
    major: str
    min_build_number: str | Unset = UNSET
    editions: list[WindowsEdition] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        major = self.major

        min_build_number = self.min_build_number

        editions: list[str] | Unset = UNSET
        if not isinstance(self.editions, Unset):
            editions = []
            for editions_item_data in self.editions:
                editions_item = editions_item_data.value
                editions.append(editions_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
                "major": major,
            }
        )
        if min_build_number is not UNSET:
            field_dict["minBuildNumber"] = min_build_number
        if editions is not UNSET:
            field_dict["editions"] = editions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        major = d.pop("major")

        min_build_number = d.pop("minBuildNumber", UNSET)

        _editions = d.pop("editions", UNSET)
        editions: list[WindowsEdition] | Unset = UNSET
        if _editions is not UNSET:
            editions = []
            for editions_item_data in _editions:
                editions_item = WindowsEdition(editions_item_data)

                editions.append(editions_item)

        windows_version = cls(
            enabled=enabled,
            major=major,
            min_build_number=min_build_number,
            editions=editions,
        )

        windows_version.additional_properties = d
        return windows_version

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
