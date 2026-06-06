from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.disk_encryption_vendor_name import DiskEncryptionVendorName
from ..types import UNSET, Unset

T = TypeVar("T", bound="AttributeObjectDiskEncryption")


@_attrs_define
class AttributeObjectDiskEncryption:
    """Check if the device has disk encryption software installed and running

    Attributes:
        enabled (bool): Whether this attribute is enabled
        negate (bool | Unset): Whether to negate this attribute Default: False.
        any_vendor (bool | Unset): Whether to accept any disk encryption vendor
        specific_vendors (list[DiskEncryptionVendorName] | Unset): Selected disk encryption vendors to check for
    """

    enabled: bool
    negate: bool | Unset = False
    any_vendor: bool | Unset = UNSET
    specific_vendors: list[DiskEncryptionVendorName] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        any_vendor = self.any_vendor

        specific_vendors: list[str] | Unset = UNSET
        if not isinstance(self.specific_vendors, Unset):
            specific_vendors = []
            for specific_vendors_item_data in self.specific_vendors:
                specific_vendors_item = specific_vendors_item_data.value
                specific_vendors.append(specific_vendors_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if any_vendor is not UNSET:
            field_dict["anyVendor"] = any_vendor
        if specific_vendors is not UNSET:
            field_dict["specificVendors"] = specific_vendors

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        any_vendor = d.pop("anyVendor", UNSET)

        _specific_vendors = d.pop("specificVendors", UNSET)
        specific_vendors: list[DiskEncryptionVendorName] | Unset = UNSET
        if _specific_vendors is not UNSET:
            specific_vendors = []
            for specific_vendors_item_data in _specific_vendors:
                specific_vendors_item = DiskEncryptionVendorName(specific_vendors_item_data)

                specific_vendors.append(specific_vendors_item)

        attribute_object_disk_encryption = cls(
            enabled=enabled,
            negate=negate,
            any_vendor=any_vendor,
            specific_vendors=specific_vendors,
        )

        attribute_object_disk_encryption.additional_properties = d
        return attribute_object_disk_encryption

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
