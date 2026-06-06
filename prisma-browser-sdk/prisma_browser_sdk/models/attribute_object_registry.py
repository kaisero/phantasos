from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.reg_key import RegKey


T = TypeVar("T", bound="AttributeObjectRegistry")


@_attrs_define
class AttributeObjectRegistry:
    """Check if the device has all of the specified registry key configurations (Windows only)

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        reg_keys (list[RegKey] | Unset): Registry key configurations to validate
    """

    enabled: bool
    negate: bool | Unset = False
    reg_keys: list[RegKey] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        reg_keys: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.reg_keys, Unset):
            reg_keys = []
            for reg_keys_item_data in self.reg_keys:
                reg_keys_item = reg_keys_item_data.to_dict()
                reg_keys.append(reg_keys_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if reg_keys is not UNSET:
            field_dict["regKeys"] = reg_keys

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.reg_key import RegKey

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _reg_keys = d.pop("regKeys", UNSET)
        reg_keys: list[RegKey] | Unset = UNSET
        if _reg_keys is not UNSET:
            reg_keys = []
            for reg_keys_item_data in _reg_keys:
                reg_keys_item = RegKey.from_dict(reg_keys_item_data)

                reg_keys.append(reg_keys_item)

        attribute_object_registry = cls(
            enabled=enabled,
            negate=negate,
            reg_keys=reg_keys,
        )

        attribute_object_registry.additional_properties = d
        return attribute_object_registry

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
