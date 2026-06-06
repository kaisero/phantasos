from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="DevicePasswordPosturePolicy")


@_attrs_define
class DevicePasswordPosturePolicy:
    """
    Attributes:
        complexity_req (bool):
        max_password_age (int):
        min_password_length (int):
    """

    complexity_req: bool
    max_password_age: int
    min_password_length: int
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        complexity_req = self.complexity_req

        max_password_age = self.max_password_age

        min_password_length = self.min_password_length

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "complexityReq": complexity_req,
                "maxPasswordAge": max_password_age,
                "minPasswordLength": min_password_length,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        complexity_req = d.pop("complexityReq")

        max_password_age = d.pop("maxPasswordAge")

        min_password_length = d.pop("minPasswordLength")

        device_password_posture_policy = cls(
            complexity_req=complexity_req,
            max_password_age=max_password_age,
            min_password_length=min_password_length,
        )

        device_password_posture_policy.additional_properties = d
        return device_password_posture_policy

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
