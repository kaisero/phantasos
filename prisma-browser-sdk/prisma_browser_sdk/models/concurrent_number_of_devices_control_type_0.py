from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.concurrent_number_of_devices_control_type_0_action import ConcurrentNumberOfDevicesControlType0Action
from ..models.concurrent_number_of_devices_control_type_0_limit_mode import (
    ConcurrentNumberOfDevicesControlType0LimitMode,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="ConcurrentNumberOfDevicesControlType0")


@_attrs_define
class ConcurrentNumberOfDevicesControlType0:
    """Control the maximum number of devices users can be logged into at the same time.

    Attributes:
        action (ConcurrentNumberOfDevicesControlType0Action): Whether to limit the number of concurrent devices.
        limit_mode (ConcurrentNumberOfDevicesControlType0LimitMode | Unset): Whether the device limit applies to all
            devices combined or per device type.
        max_total_devices (int | Unset): Maximum total number of devices a user can be logged into across all device
            types.
        max_desktop_devices (int | None | Unset): Maximum number of desktop devices (macOS/Windows/Linux). Use null for
            no limit, or 0 to block desktop devices entirely.
        max_mobile_devices (int | None | Unset): Maximum number of mobile devices (iOS/Android). Use null for no limit,
            or 0 to block mobile devices entirely.
    """

    action: ConcurrentNumberOfDevicesControlType0Action
    limit_mode: ConcurrentNumberOfDevicesControlType0LimitMode | Unset = UNSET
    max_total_devices: int | Unset = UNSET
    max_desktop_devices: int | None | Unset = UNSET
    max_mobile_devices: int | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        limit_mode: str | Unset = UNSET
        if not isinstance(self.limit_mode, Unset):
            limit_mode = self.limit_mode.value

        max_total_devices = self.max_total_devices

        max_desktop_devices: int | None | Unset
        if isinstance(self.max_desktop_devices, Unset):
            max_desktop_devices = UNSET
        else:
            max_desktop_devices = self.max_desktop_devices

        max_mobile_devices: int | None | Unset
        if isinstance(self.max_mobile_devices, Unset):
            max_mobile_devices = UNSET
        else:
            max_mobile_devices = self.max_mobile_devices

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if limit_mode is not UNSET:
            field_dict["limitMode"] = limit_mode
        if max_total_devices is not UNSET:
            field_dict["maxTotalDevices"] = max_total_devices
        if max_desktop_devices is not UNSET:
            field_dict["maxDesktopDevices"] = max_desktop_devices
        if max_mobile_devices is not UNSET:
            field_dict["maxMobileDevices"] = max_mobile_devices

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = ConcurrentNumberOfDevicesControlType0Action(d.pop("action"))

        _limit_mode = d.pop("limitMode", UNSET)
        limit_mode: ConcurrentNumberOfDevicesControlType0LimitMode | Unset
        if isinstance(_limit_mode, Unset):
            limit_mode = UNSET
        else:
            limit_mode = ConcurrentNumberOfDevicesControlType0LimitMode(_limit_mode)

        max_total_devices = d.pop("maxTotalDevices", UNSET)

        def _parse_max_desktop_devices(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_desktop_devices = _parse_max_desktop_devices(d.pop("maxDesktopDevices", UNSET))

        def _parse_max_mobile_devices(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        max_mobile_devices = _parse_max_mobile_devices(d.pop("maxMobileDevices", UNSET))

        concurrent_number_of_devices_control_type_0 = cls(
            action=action,
            limit_mode=limit_mode,
            max_total_devices=max_total_devices,
            max_desktop_devices=max_desktop_devices,
            max_mobile_devices=max_mobile_devices,
        )

        return concurrent_number_of_devices_control_type_0
