from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.mobile_os import MobileOs


T = TypeVar("T", bound="MobileOsVersion")


@_attrs_define
class MobileOsVersion:
    """
    Attributes:
        any_ (bool):
        os (list[MobileOs]):
    """

    any_: bool
    os: list[MobileOs]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        any_ = self.any_

        os = []
        for os_item_data in self.os:
            os_item = os_item_data.to_dict()
            os.append(os_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "any": any_,
                "os": os,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.mobile_os import MobileOs

        d = dict(src_dict)
        any_ = d.pop("any")

        os = []
        _os = d.pop("os")
        for os_item_data in _os:
            os_item = MobileOs.from_dict(os_item_data)

            os.append(os_item)

        mobile_os_version = cls(
            any_=any_,
            os=os,
        )

        mobile_os_version.additional_properties = d
        return mobile_os_version

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
