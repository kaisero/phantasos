from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.firewall_vendor_name import FirewallVendorName

T = TypeVar("T", bound="FirewallProduct")


@_attrs_define
class FirewallProduct:
    """Firewall product information

    Attributes:
        vendor_name (FirewallVendorName): Firewall vendor name
        product_name (str): Product name of the firewall
        enabled (bool): Whether the firewall is enabled
    """

    vendor_name: FirewallVendorName
    product_name: str
    enabled: bool
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        vendor_name = self.vendor_name.value

        product_name = self.product_name

        enabled = self.enabled

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "vendorName": vendor_name,
                "productName": product_name,
                "enabled": enabled,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        vendor_name = FirewallVendorName(d.pop("vendorName"))

        product_name = d.pop("productName")

        enabled = d.pop("enabled")

        firewall_product = cls(
            vendor_name=vendor_name,
            product_name=product_name,
            enabled=enabled,
        )

        firewall_product.additional_properties = d
        return firewall_product

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
