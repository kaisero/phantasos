from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.add_remove_apps import AddRemoveApps


T = TypeVar("T", bound="PatchAppGroupInput")


@_attrs_define
class PatchAppGroupInput:
    """
    Attributes:
        name (str | Unset): Name of the application group
        description (str | Unset): Description of the application group
        applications (AddRemoveApps | list[str] | Unset):
    """

    name: str | Unset = UNSET
    description: str | Unset = UNSET
    applications: AddRemoveApps | list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.add_remove_apps import AddRemoveApps

        name = self.name

        description = self.description

        applications: dict[str, Any] | list[str] | Unset
        if isinstance(self.applications, Unset):
            applications = UNSET
        elif isinstance(self.applications, AddRemoveApps):
            applications = self.applications.to_dict()
        else:
            applications = self.applications

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if applications is not UNSET:
            field_dict["applications"] = applications

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.add_remove_apps import AddRemoveApps

        d = dict(src_dict)
        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        def _parse_applications(data: object) -> AddRemoveApps | list[str] | Unset:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                applications_type_0 = AddRemoveApps.from_dict(data)

                return applications_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, list):
                raise TypeError()
            applications_type_1 = cast(list[str], data)

            return applications_type_1

        applications = _parse_applications(d.pop("applications", UNSET))

        patch_app_group_input = cls(
            name=name,
            description=description,
            applications=applications,
        )

        patch_app_group_input.additional_properties = d
        return patch_app_group_input

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
