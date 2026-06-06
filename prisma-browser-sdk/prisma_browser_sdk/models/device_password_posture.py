from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.device_password_posture_policy import DevicePasswordPosturePolicy


T = TypeVar("T", bound="DevicePasswordPosture")


@_attrs_define
class DevicePasswordPosture:
    """
    Attributes:
        enabled (bool):
        password_policy (DevicePasswordPosturePolicy | Unset):
    """

    enabled: bool
    password_policy: DevicePasswordPosturePolicy | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        password_policy: dict[str, Any] | Unset = UNSET
        if not isinstance(self.password_policy, Unset):
            password_policy = self.password_policy.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if password_policy is not UNSET:
            field_dict["passwordPolicy"] = password_policy

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.device_password_posture_policy import DevicePasswordPosturePolicy

        d = dict(src_dict)
        enabled = d.pop("enabled")

        _password_policy = d.pop("passwordPolicy", UNSET)
        password_policy: DevicePasswordPosturePolicy | Unset
        if isinstance(_password_policy, Unset):
            password_policy = UNSET
        else:
            password_policy = DevicePasswordPosturePolicy.from_dict(_password_policy)

        device_password_posture = cls(
            enabled=enabled,
            password_policy=password_policy,
        )

        device_password_posture.additional_properties = d
        return device_password_posture

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
