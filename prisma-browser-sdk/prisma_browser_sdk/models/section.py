from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.section_type import SectionType
from ..types import UNSET, Unset

T = TypeVar("T", bound="Section")


@_attrs_define
class Section:
    """A container to group related rules for organizational purposes.

    Attributes:
        id (str): The unique identifier for the policy item.
        position (int): 1-based index of this item in the flat list. Example: 2.
        type_ (SectionType): Discriminator field, must be 'Section'.
        name (str | Unset): The name or title of the rule or section.
    """

    id: str
    position: int
    type_: SectionType
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        position = self.position

        type_ = self.type_.value

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "position": position,
                "type": type_,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        position = d.pop("position")

        type_ = SectionType(d.pop("type"))

        name = d.pop("name", UNSET)

        section = cls(
            id=id,
            position=position,
            type_=type_,
            name=name,
        )

        section.additional_properties = d
        return section

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
