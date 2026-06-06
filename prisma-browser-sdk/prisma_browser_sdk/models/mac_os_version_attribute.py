from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.mac_os_version import MacOSVersion


T = TypeVar("T", bound="MacOSVersionAttribute")


@_attrs_define
class MacOSVersionAttribute:
    """
    Attributes:
        any_ (bool | Unset):  Default: False.
        versions (list[MacOSVersion] | Unset):
    """

    any_: bool | Unset = False
    versions: list[MacOSVersion] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        any_ = self.any_

        versions: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.versions, Unset):
            versions = []
            for versions_item_data in self.versions:
                versions_item = versions_item_data.to_dict()
                versions.append(versions_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if any_ is not UNSET:
            field_dict["any"] = any_
        if versions is not UNSET:
            field_dict["versions"] = versions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.mac_os_version import MacOSVersion

        d = dict(src_dict)
        any_ = d.pop("any", UNSET)

        _versions = d.pop("versions", UNSET)
        versions: list[MacOSVersion] | Unset = UNSET
        if _versions is not UNSET:
            versions = []
            for versions_item_data in _versions:
                versions_item = MacOSVersion.from_dict(versions_item_data)

                versions.append(versions_item)

        mac_os_version_attribute = cls(
            any_=any_,
            versions=versions,
        )

        mac_os_version_attribute.additional_properties = d
        return mac_os_version_attribute

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
