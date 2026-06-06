from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.application_group_applications_item import ApplicationGroupApplicationsItem
    from ..models.metadata import Metadata


T = TypeVar("T", bound="ApplicationGroup")


@_attrs_define
class ApplicationGroup:
    """
    Attributes:
        id (str): Unique identifier
        name (str): Name of the application group
        metadata (Metadata):
        description (str | Unset): Description of the application group
        applications (list[ApplicationGroupApplicationsItem] | Unset): IDs of the group members
    """

    id: str
    name: str
    metadata: Metadata
    description: str | Unset = UNSET
    applications: list[ApplicationGroupApplicationsItem] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        metadata = self.metadata.to_dict()

        description = self.description

        applications: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.applications, Unset):
            applications = []
            for applications_item_data in self.applications:
                applications_item = applications_item_data.to_dict()
                applications.append(applications_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "metadata": metadata,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if applications is not UNSET:
            field_dict["applications"] = applications

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.application_group_applications_item import ApplicationGroupApplicationsItem
        from ..models.metadata import Metadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        metadata = Metadata.from_dict(d.pop("metadata"))

        description = d.pop("description", UNSET)

        _applications = d.pop("applications", UNSET)
        applications: list[ApplicationGroupApplicationsItem] | Unset = UNSET
        if _applications is not UNSET:
            applications = []
            for applications_item_data in _applications:
                applications_item = ApplicationGroupApplicationsItem.from_dict(applications_item_data)

                applications.append(applications_item)

        application_group = cls(
            id=id,
            name=name,
            metadata=metadata,
            description=description,
            applications=applications,
        )

        application_group.additional_properties = d
        return application_group

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
