from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.linux_distro import LinuxDistro
from ..types import UNSET, Unset

T = TypeVar("T", bound="LinuxVersion")


@_attrs_define
class LinuxVersion:
    """
    Attributes:
        enabled (bool):
        distro (LinuxDistro | Unset): Linux distribution
        min_version (str | Unset): Minimum Linux version (e.g., "20.04" for Ubuntu, "33" for Fedora)
    """

    enabled: bool
    distro: LinuxDistro | Unset = UNSET
    min_version: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        distro: str | Unset = UNSET
        if not isinstance(self.distro, Unset):
            distro = self.distro.value

        min_version = self.min_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if distro is not UNSET:
            field_dict["distro"] = distro
        if min_version is not UNSET:
            field_dict["minVersion"] = min_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        _distro = d.pop("distro", UNSET)
        distro: LinuxDistro | Unset
        if isinstance(_distro, Unset):
            distro = UNSET
        else:
            distro = LinuxDistro(_distro)

        min_version = d.pop("minVersion", UNSET)

        linux_version = cls(
            enabled=enabled,
            distro=distro,
            min_version=min_version,
        )

        linux_version.additional_properties = d
        return linux_version

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
