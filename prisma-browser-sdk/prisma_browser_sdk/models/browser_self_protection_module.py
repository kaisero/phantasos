from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.browser_self_protection_module_windows import BrowserSelfProtectionModuleWindows


T = TypeVar("T", bound="BrowserSelfProtectionModule")


@_attrs_define
class BrowserSelfProtectionModule:
    """Browser self-protection module

    Attributes:
        windows (BrowserSelfProtectionModuleWindows | Unset): Windows driver info
    """

    windows: BrowserSelfProtectionModuleWindows | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        windows: dict[str, Any] | Unset = UNSET
        if not isinstance(self.windows, Unset):
            windows = self.windows.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if windows is not UNSET:
            field_dict["windows"] = windows

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.browser_self_protection_module_windows import BrowserSelfProtectionModuleWindows

        d = dict(src_dict)
        _windows = d.pop("windows", UNSET)
        windows: BrowserSelfProtectionModuleWindows | Unset
        if isinstance(_windows, Unset):
            windows = UNSET
        else:
            windows = BrowserSelfProtectionModuleWindows.from_dict(_windows)

        browser_self_protection_module = cls(
            windows=windows,
        )

        browser_self_protection_module.additional_properties = d
        return browser_self_protection_module

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
