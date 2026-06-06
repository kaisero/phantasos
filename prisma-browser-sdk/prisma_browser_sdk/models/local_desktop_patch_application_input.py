from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.local_desktop_type_input import LocalDesktopTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.local_desktop_app_executables_input import LocalDesktopAppExecutablesInput


T = TypeVar("T", bound="LocalDesktopPatchApplicationInput")


@_attrs_define
class LocalDesktopPatchApplicationInput:
    """
    Attributes:
        type_ (LocalDesktopTypeInput): Discriminator field, must be 'localdesktopcustom'.
        name (str | Unset): Name of the application
        description (str | Unset): Description of the application
        executables (LocalDesktopAppExecutablesInput | Unset):
        category (str | Unset):
    """

    type_: LocalDesktopTypeInput
    name: str | Unset = UNSET
    description: str | Unset = UNSET
    executables: LocalDesktopAppExecutablesInput | Unset = UNSET
    category: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        name = self.name

        description = self.description

        executables: dict[str, Any] | Unset = UNSET
        if not isinstance(self.executables, Unset):
            executables = self.executables.to_dict()

        category = self.category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if executables is not UNSET:
            field_dict["executables"] = executables
        if category is not UNSET:
            field_dict["category"] = category

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.local_desktop_app_executables_input import LocalDesktopAppExecutablesInput

        d = dict(src_dict)
        type_ = LocalDesktopTypeInput(d.pop("type"))

        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        _executables = d.pop("executables", UNSET)
        executables: LocalDesktopAppExecutablesInput | Unset
        if isinstance(_executables, Unset):
            executables = UNSET
        else:
            executables = LocalDesktopAppExecutablesInput.from_dict(_executables)

        category = d.pop("category", UNSET)

        local_desktop_patch_application_input = cls(
            type_=type_,
            name=name,
            description=description,
            executables=executables,
            category=category,
        )

        local_desktop_patch_application_input.additional_properties = d
        return local_desktop_patch_application_input

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
