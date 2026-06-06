from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.registry_value_type import RegistryValueType
from ..types import UNSET, Unset

T = TypeVar("T", bound="RegValue")


@_attrs_define
class RegValue:
    """
    Attributes:
        name (str):
        data (str | Unset):
        type_ (RegistryValueType | Unset): Registry value type
    """

    name: str
    data: str | Unset = UNSET
    type_: RegistryValueType | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        data = self.data

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if data is not UNSET:
            field_dict["data"] = data
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        data = d.pop("data", UNSET)

        _type_ = d.pop("type", UNSET)
        type_: RegistryValueType | Unset
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = RegistryValueType(_type_)

        reg_value = cls(
            name=name,
            data=data,
            type_=type_,
        )

        reg_value.additional_properties = d
        return reg_value

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
