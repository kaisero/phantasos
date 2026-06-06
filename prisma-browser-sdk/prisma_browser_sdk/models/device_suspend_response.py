from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="DeviceSuspendResponse")


@_attrs_define
class DeviceSuspendResponse:
    """
    Attributes:
        suspended_device_ids (list[str] | Unset): List of device IDs that were suspended
        message (str | Unset):  Example: 3 devices suspended successfully.
    """

    suspended_device_ids: list[str] | Unset = UNSET
    message: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        suspended_device_ids: list[str] | Unset = UNSET
        if not isinstance(self.suspended_device_ids, Unset):
            suspended_device_ids = self.suspended_device_ids

        message = self.message

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if suspended_device_ids is not UNSET:
            field_dict["suspendedDeviceIds"] = suspended_device_ids
        if message is not UNSET:
            field_dict["message"] = message

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        suspended_device_ids = cast(list[str], d.pop("suspendedDeviceIds", UNSET))

        message = d.pop("message", UNSET)

        device_suspend_response = cls(
            suspended_device_ids=suspended_device_ids,
            message=message,
        )

        device_suspend_response.additional_properties = d
        return device_suspend_response

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
