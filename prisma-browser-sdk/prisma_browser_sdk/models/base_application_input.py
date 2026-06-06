from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.application_type_input import ApplicationTypeInput
from ..types import UNSET, Unset

T = TypeVar("T", bound="BaseApplicationInput")


@_attrs_define
class BaseApplicationInput:
    """
    Attributes:
        name (str): Name of the application
        type_ (ApplicationTypeInput):
        description (str | Unset): Description of the application
    """

    name: str
    type_: ApplicationTypeInput
    description: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_.value

        description = self.description

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "type": type_,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        type_ = ApplicationTypeInput(d.pop("type"))

        description = d.pop("description", UNSET)

        base_application_input = cls(
            name=name,
            type_=type_,
            description=description,
        )

        base_application_input.additional_properties = d
        return base_application_input

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
