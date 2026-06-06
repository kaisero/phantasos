from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MacOSFileExistenceMetadata")


@_attrs_define
class MacOSFileExistenceMetadata:
    """
    Attributes:
        path (str): Full path to the file on macOS
        team_identifier (str | Unset): Apple Team Identifier to validate the file signature
    """

    path: str
    team_identifier: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        path = self.path

        team_identifier = self.team_identifier

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "path": path,
            }
        )
        if team_identifier is not UNSET:
            field_dict["teamIdentifier"] = team_identifier

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        path = d.pop("path")

        team_identifier = d.pop("teamIdentifier", UNSET)

        mac_os_file_existence_metadata = cls(
            path=path,
            team_identifier=team_identifier,
        )

        mac_os_file_existence_metadata.additional_properties = d
        return mac_os_file_existence_metadata

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
