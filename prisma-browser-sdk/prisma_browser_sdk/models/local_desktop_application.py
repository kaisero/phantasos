from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.local_desktop_application_type import LocalDesktopApplicationType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.local_desktop_application_executables import LocalDesktopApplicationExecutables
    from ..models.metadata import Metadata


T = TypeVar("T", bound="LocalDesktopApplication")


@_attrs_define
class LocalDesktopApplication:
    """Local Desktop Application

    Attributes:
        id (str): Unique identifier
        name (str): Name of the application
        type_ (LocalDesktopApplicationType): Discriminator field, must be 'localdesktopcustom'.
        metadata (Metadata):
        executables (LocalDesktopApplicationExecutables): Local Desktop Application Executables
        description (str | Unset): Description of the application
        category (str | Unset):
    """

    id: str
    name: str
    type_: LocalDesktopApplicationType
    metadata: Metadata
    executables: LocalDesktopApplicationExecutables
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        type_ = self.type_.value

        metadata = self.metadata.to_dict()

        executables = self.executables.to_dict()

        description = self.description

        category = self.category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "type": type_,
                "metadata": metadata,
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
        from ..models.local_desktop_application_executables import LocalDesktopApplicationExecutables
        from ..models.metadata import Metadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        type_ = LocalDesktopApplicationType(d.pop("type"))

        metadata = Metadata.from_dict(d.pop("metadata"))

        executables = LocalDesktopApplicationExecutables.from_dict(d.pop("executables"))

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        local_desktop_application = cls(
            id=id,
            name=name,
            type_=type_,
            metadata=metadata,
            executables=executables,
            description=description,
            category=category,
        )

        local_desktop_application.additional_properties = d
        return local_desktop_application

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
