from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.os_password_complexity import OsPasswordComplexity


T = TypeVar("T", bound="AttributeObjectOsPassword")


@_attrs_define
class AttributeObjectOsPassword:
    """Check if the device has an OS authentication password configured with specific requirements

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        complexity (OsPasswordComplexity | Unset):
        max_age (int | Unset): Maximum password age in days
        min_length (int | Unset): Minimum password length in characters
    """

    enabled: bool
    negate: bool | Unset = False
    complexity: OsPasswordComplexity | Unset = UNSET
    max_age: int | Unset = UNSET
    min_length: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        complexity: dict[str, Any] | Unset = UNSET
        if not isinstance(self.complexity, Unset):
            complexity = self.complexity.to_dict()

        max_age = self.max_age

        min_length = self.min_length

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if complexity is not UNSET:
            field_dict["complexity"] = complexity
        if max_age is not UNSET:
            field_dict["maxAge"] = max_age
        if min_length is not UNSET:
            field_dict["minLength"] = min_length

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.os_password_complexity import OsPasswordComplexity

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _complexity = d.pop("complexity", UNSET)
        complexity: OsPasswordComplexity | Unset
        if isinstance(_complexity, Unset):
            complexity = UNSET
        else:
            complexity = OsPasswordComplexity.from_dict(_complexity)

        max_age = d.pop("maxAge", UNSET)

        min_length = d.pop("minLength", UNSET)

        attribute_object_os_password = cls(
            enabled=enabled,
            negate=negate,
            complexity=complexity,
            max_age=max_age,
            min_length=min_length,
        )

        attribute_object_os_password.additional_properties = d
        return attribute_object_os_password

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
