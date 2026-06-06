from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateOrReplaceAppGroupInput")


@_attrs_define
class CreateOrReplaceAppGroupInput:
    """
    Attributes:
        name (str): Name of the application group
        description (str | Unset): Description of the application group
        applications (list[str] | Unset): List of member application IDs
    """

    name: str
    description: str | Unset = UNSET
    applications: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        description = self.description

        applications: list[str] | Unset = UNSET
        if not isinstance(self.applications, Unset):
            applications = self.applications

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if applications is not UNSET:
            field_dict["applications"] = applications

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        description = d.pop("description", UNSET)

        applications = cast(list[str], d.pop("applications", UNSET))

        create_or_replace_app_group_input = cls(
            name=name,
            description=description,
            applications=applications,
        )

        create_or_replace_app_group_input.additional_properties = d
        return create_or_replace_app_group_input

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
