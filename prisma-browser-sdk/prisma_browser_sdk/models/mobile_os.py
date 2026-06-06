from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="MobileOs")


@_attrs_define
class MobileOs:
    """
    Attributes:
        enabled (bool):
        version (str):
        min_security_patch (str | Unset):
        latest (bool | Unset):
    """

    enabled: bool
    version: str
    min_security_patch: str | Unset = UNSET
    latest: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        version = self.version

        min_security_patch = self.min_security_patch

        latest = self.latest

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
                "version": version,
            }
        )
        if min_security_patch is not UNSET:
            field_dict["minSecurityPatch"] = min_security_patch
        if latest is not UNSET:
            field_dict["latest"] = latest

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        version = d.pop("version")

        min_security_patch = d.pop("minSecurityPatch", UNSET)

        latest = d.pop("latest", UNSET)

        mobile_os = cls(
            enabled=enabled,
            version=version,
            min_security_patch=min_security_patch,
            latest=latest,
        )

        mobile_os.additional_properties = d
        return mobile_os

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
