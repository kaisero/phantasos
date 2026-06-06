from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.mac_os_running_process_metadata import MacOSRunningProcessMetadata
    from ..models.win_running_process_metadata import WinRunningProcessMetadata


T = TypeVar("T", bound="AttributeObjectRunningProcesses")


@_attrs_define
class AttributeObjectRunningProcesses:
    """Check if the device has all of the specified processes running

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        win (list[WinRunningProcessMetadata] | Unset): Windows process requirements to check for
        mac_os (list[MacOSRunningProcessMetadata] | Unset): macOS process requirements to check for
    """

    enabled: bool
    negate: bool | Unset = False
    win: list[WinRunningProcessMetadata] | Unset = UNSET
    mac_os: list[MacOSRunningProcessMetadata] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        win: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.win, Unset):
            win = []
            for win_item_data in self.win:
                win_item = win_item_data.to_dict()
                win.append(win_item)

        mac_os: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.mac_os, Unset):
            mac_os = []
            for mac_os_item_data in self.mac_os:
                mac_os_item = mac_os_item_data.to_dict()
                mac_os.append(mac_os_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if win is not UNSET:
            field_dict["win"] = win
        if mac_os is not UNSET:
            field_dict["macOS"] = mac_os

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.mac_os_running_process_metadata import MacOSRunningProcessMetadata
        from ..models.win_running_process_metadata import WinRunningProcessMetadata

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _win = d.pop("win", UNSET)
        win: list[WinRunningProcessMetadata] | Unset = UNSET
        if _win is not UNSET:
            win = []
            for win_item_data in _win:
                win_item = WinRunningProcessMetadata.from_dict(win_item_data)

                win.append(win_item)

        _mac_os = d.pop("macOS", UNSET)
        mac_os: list[MacOSRunningProcessMetadata] | Unset = UNSET
        if _mac_os is not UNSET:
            mac_os = []
            for mac_os_item_data in _mac_os:
                mac_os_item = MacOSRunningProcessMetadata.from_dict(mac_os_item_data)

                mac_os.append(mac_os_item)

        attribute_object_running_processes = cls(
            enabled=enabled,
            negate=negate,
            win=win,
            mac_os=mac_os,
        )

        attribute_object_running_processes.additional_properties = d
        return attribute_object_running_processes

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
