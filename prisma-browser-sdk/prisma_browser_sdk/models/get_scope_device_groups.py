from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.device_group_ref import DeviceGroupRef


T = TypeVar("T", bound="GetScopeDeviceGroups")


@_attrs_define
class GetScopeDeviceGroups:
    """The device groups the rule applies to.

    Attributes:
        is_any (bool): Flag indicating if any device groups are included in the scope.
        device_groups (list[DeviceGroupRef]): Device groups the rule applies to.
    """

    is_any: bool
    device_groups: list[DeviceGroupRef]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_any = self.is_any

        device_groups = []
        for device_groups_item_data in self.device_groups:
            device_groups_item = device_groups_item_data.to_dict()
            device_groups.append(device_groups_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "isAny": is_any,
                "deviceGroups": device_groups,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.device_group_ref import DeviceGroupRef

        d = dict(src_dict)
        is_any = d.pop("isAny")

        device_groups = []
        _device_groups = d.pop("deviceGroups")
        for device_groups_item_data in _device_groups:
            device_groups_item = DeviceGroupRef.from_dict(device_groups_item_data)

            device_groups.append(device_groups_item)

        get_scope_device_groups = cls(
            is_any=is_any,
            device_groups=device_groups,
        )

        get_scope_device_groups.additional_properties = d
        return get_scope_device_groups

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
