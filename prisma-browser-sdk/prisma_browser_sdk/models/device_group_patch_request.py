from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.attribute_object import AttributeObject


T = TypeVar("T", bound="DeviceGroupPatchRequest")


@_attrs_define
class DeviceGroupPatchRequest:
    """
    Attributes:
        name (str | Unset): Device group name
        attributes (AttributeObject | Unset):
        serials_to_add (list[str] | Unset): Serial numbers to add to the device group. Idempotent - adding existing
            serials has no effect. Example: ['LAPTOP001', 'LAPTOP002', 'DESKTOP001'].
        serials_to_remove (list[str] | Unset): Serial numbers to remove from the device group. Idempotent - removing
            non-existing serials has no effect. Example: ['LAPTOP001', 'DESKTOP001'].
    """

    name: str | Unset = UNSET
    attributes: AttributeObject | Unset = UNSET
    serials_to_add: list[str] | Unset = UNSET
    serials_to_remove: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        attributes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        serials_to_add: list[str] | Unset = UNSET
        if not isinstance(self.serials_to_add, Unset):
            serials_to_add = self.serials_to_add

        serials_to_remove: list[str] | Unset = UNSET
        if not isinstance(self.serials_to_remove, Unset):
            serials_to_remove = self.serials_to_remove

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if attributes is not UNSET:
            field_dict["attributes"] = attributes
        if serials_to_add is not UNSET:
            field_dict["serialsToAdd"] = serials_to_add
        if serials_to_remove is not UNSET:
            field_dict["serialsToRemove"] = serials_to_remove

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.attribute_object import AttributeObject

        d = dict(src_dict)
        name = d.pop("name", UNSET)

        _attributes = d.pop("attributes", UNSET)
        attributes: AttributeObject | Unset
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = AttributeObject.from_dict(_attributes)

        serials_to_add = cast(list[str], d.pop("serialsToAdd", UNSET))

        serials_to_remove = cast(list[str], d.pop("serialsToRemove", UNSET))

        device_group_patch_request = cls(
            name=name,
            attributes=attributes,
            serials_to_add=serials_to_add,
            serials_to_remove=serials_to_remove,
        )

        device_group_patch_request.additional_properties = d
        return device_group_patch_request

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
