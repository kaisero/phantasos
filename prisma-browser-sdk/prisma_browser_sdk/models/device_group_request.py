from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.device_group_platform import DeviceGroupPlatform
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.attribute_object import AttributeObject


T = TypeVar("T", bound="DeviceGroupRequest")


@_attrs_define
class DeviceGroupRequest:
    """
    Attributes:
        name (str): Device group name
        platform (DeviceGroupPlatform): Device group platform
        attributes (AttributeObject | Unset):
    """

    name: str
    platform: DeviceGroupPlatform
    attributes: AttributeObject | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        platform = self.platform.value

        attributes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "platform": platform,
            }
        )
        if attributes is not UNSET:
            field_dict["attributes"] = attributes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.attribute_object import AttributeObject

        d = dict(src_dict)
        name = d.pop("name")

        platform = DeviceGroupPlatform(d.pop("platform"))

        _attributes = d.pop("attributes", UNSET)
        attributes: AttributeObject | Unset
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = AttributeObject.from_dict(_attributes)

        device_group_request = cls(
            name=name,
            platform=platform,
            attributes=attributes,
        )

        device_group_request.additional_properties = d
        return device_group_request

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
