from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.linux_version_attribute import LinuxVersionAttribute
    from ..models.mac_os_version_attribute import MacOSVersionAttribute
    from ..models.windows_version_attribute import WindowsVersionAttribute


T = TypeVar("T", bound="AttributeObjectOsVersion")


@_attrs_define
class AttributeObjectOsVersion:
    """Check if the device is running a specific operating system version

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        windows (WindowsVersionAttribute | Unset):
        mac_os (MacOSVersionAttribute | Unset):
        linux (LinuxVersionAttribute | Unset):
    """

    enabled: bool
    negate: bool | Unset = False
    windows: WindowsVersionAttribute | Unset = UNSET
    mac_os: MacOSVersionAttribute | Unset = UNSET
    linux: LinuxVersionAttribute | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        windows: dict[str, Any] | Unset = UNSET
        if not isinstance(self.windows, Unset):
            windows = self.windows.to_dict()

        mac_os: dict[str, Any] | Unset = UNSET
        if not isinstance(self.mac_os, Unset):
            mac_os = self.mac_os.to_dict()

        linux: dict[str, Any] | Unset = UNSET
        if not isinstance(self.linux, Unset):
            linux = self.linux.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if windows is not UNSET:
            field_dict["windows"] = windows
        if mac_os is not UNSET:
            field_dict["macOS"] = mac_os
        if linux is not UNSET:
            field_dict["linux"] = linux

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.linux_version_attribute import LinuxVersionAttribute
        from ..models.mac_os_version_attribute import MacOSVersionAttribute
        from ..models.windows_version_attribute import WindowsVersionAttribute

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _windows = d.pop("windows", UNSET)
        windows: WindowsVersionAttribute | Unset
        if isinstance(_windows, Unset):
            windows = UNSET
        else:
            windows = WindowsVersionAttribute.from_dict(_windows)

        _mac_os = d.pop("macOS", UNSET)
        mac_os: MacOSVersionAttribute | Unset
        if isinstance(_mac_os, Unset):
            mac_os = UNSET
        else:
            mac_os = MacOSVersionAttribute.from_dict(_mac_os)

        _linux = d.pop("linux", UNSET)
        linux: LinuxVersionAttribute | Unset
        if isinstance(_linux, Unset):
            linux = UNSET
        else:
            linux = LinuxVersionAttribute.from_dict(_linux)

        attribute_object_os_version = cls(
            enabled=enabled,
            negate=negate,
            windows=windows,
            mac_os=mac_os,
            linux=linux,
        )

        attribute_object_os_version.additional_properties = d
        return attribute_object_os_version

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
