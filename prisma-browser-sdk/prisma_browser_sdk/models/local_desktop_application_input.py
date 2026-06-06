from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.local_desktop_type_input import LocalDesktopTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.local_desktop_app_executables_input import LocalDesktopAppExecutablesInput


T = TypeVar("T", bound="LocalDesktopApplicationInput")


@_attrs_define
class LocalDesktopApplicationInput:
    """
    Attributes:
        name (str): Name of the application
        type_ (LocalDesktopTypeInput): Discriminator field, must be 'localdesktopcustom'.
        executables (LocalDesktopAppExecutablesInput):
        description (str | Unset): Description of the application
        category (str | Unset):
    """

    name: str
    type_: LocalDesktopTypeInput
    executables: LocalDesktopAppExecutablesInput
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_.value

        executables = self.executables.to_dict()

        description = self.description

        category = self.category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "type": type_,
                "executables": executables,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if category is not UNSET:
            field_dict["category"] = category

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.local_desktop_app_executables_input import LocalDesktopAppExecutablesInput

        d = dict(src_dict)
        name = d.pop("name")

        type_ = LocalDesktopTypeInput(d.pop("type"))

        executables = LocalDesktopAppExecutablesInput.from_dict(d.pop("executables"))

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        local_desktop_application_input = cls(
            name=name,
            type_=type_,
            executables=executables,
            description=description,
            category=category,
        )

        local_desktop_application_input.additional_properties = d
        return local_desktop_application_input

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
