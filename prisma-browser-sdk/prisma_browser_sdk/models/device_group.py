from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.device_group_platform import DeviceGroupPlatform
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.attribute_object import AttributeObject


T = TypeVar("T", bound="DeviceGroup")


@_attrs_define
class DeviceGroup:
    """
    Attributes:
        id (str): Unique identifier
        name (str): Device group name
        platform (DeviceGroupPlatform): Device group platform
        created_at (datetime.datetime): Created at timestamp
        updated_at (datetime.datetime): Updated at timestamp
        created_by (str | Unset): Created by user
        updated_by (str | Unset): Updated by user
        attributes (AttributeObject | Unset):
        devices (list[str] | Unset): Device IDs in this group
    """

    id: str
    name: str
    platform: DeviceGroupPlatform
    created_at: datetime.datetime
    updated_at: datetime.datetime
    created_by: str | Unset = UNSET
    updated_by: str | Unset = UNSET
    attributes: AttributeObject | Unset = UNSET
    devices: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        platform = self.platform.value

        created_at = self.created_at.isoformat()

        updated_at = self.updated_at.isoformat()

        created_by = self.created_by

        updated_by = self.updated_by

        attributes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        devices: list[str] | Unset = UNSET
        if not isinstance(self.devices, Unset):
            devices = self.devices

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "platform": platform,
                "createdAt": created_at,
                "updatedAt": updated_at,
            }
        )
        if created_by is not UNSET:
            field_dict["createdBy"] = created_by
        if updated_by is not UNSET:
            field_dict["updatedBy"] = updated_by
        if attributes is not UNSET:
            field_dict["attributes"] = attributes
        if devices is not UNSET:
            field_dict["devices"] = devices

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.attribute_object import AttributeObject

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        platform = DeviceGroupPlatform(d.pop("platform"))

        created_at = datetime.datetime.fromisoformat(d.pop("createdAt"))

        updated_at = datetime.datetime.fromisoformat(d.pop("updatedAt"))

        created_by = d.pop("createdBy", UNSET)

        updated_by = d.pop("updatedBy", UNSET)

        _attributes = d.pop("attributes", UNSET)
        attributes: AttributeObject | Unset
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = AttributeObject.from_dict(_attributes)

        devices = cast(list[str], d.pop("devices", UNSET))

        device_group = cls(
            id=id,
            name=name,
            platform=platform,
            created_at=created_at,
            updated_at=updated_at,
            created_by=created_by,
            updated_by=updated_by,
            attributes=attributes,
            devices=devices,
        )

        device_group.additional_properties = d
        return device_group

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
