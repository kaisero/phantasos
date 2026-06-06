from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.epp_vendor_name import EppVendorName
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.last_definition_update_attribute import LastDefinitionUpdateAttribute


T = TypeVar("T", bound="AttributeObjectEndpointProtection")


@_attrs_define
class AttributeObjectEndpointProtection:
    """Check if the device has endpoint protection software installed and running

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        selected_vendors (list[EppVendorName] | Unset): Selected endpoint protection vendors to check for
        last_definition_update (LastDefinitionUpdateAttribute | Unset):
    """

    enabled: bool
    negate: bool | Unset = False
    selected_vendors: list[EppVendorName] | Unset = UNSET
    last_definition_update: LastDefinitionUpdateAttribute | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        selected_vendors: list[str] | Unset = UNSET
        if not isinstance(self.selected_vendors, Unset):
            selected_vendors = []
            for selected_vendors_item_data in self.selected_vendors:
                selected_vendors_item = selected_vendors_item_data.value
                selected_vendors.append(selected_vendors_item)

        last_definition_update: dict[str, Any] | Unset = UNSET
        if not isinstance(self.last_definition_update, Unset):
            last_definition_update = self.last_definition_update.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if selected_vendors is not UNSET:
            field_dict["selectedVendors"] = selected_vendors
        if last_definition_update is not UNSET:
            field_dict["lastDefinitionUpdate"] = last_definition_update

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.last_definition_update_attribute import LastDefinitionUpdateAttribute

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _selected_vendors = d.pop("selectedVendors", UNSET)
        selected_vendors: list[EppVendorName] | Unset = UNSET
        if _selected_vendors is not UNSET:
            selected_vendors = []
            for selected_vendors_item_data in _selected_vendors:
                selected_vendors_item = EppVendorName(selected_vendors_item_data)

                selected_vendors.append(selected_vendors_item)

        _last_definition_update = d.pop("lastDefinitionUpdate", UNSET)
        last_definition_update: LastDefinitionUpdateAttribute | Unset
        if isinstance(_last_definition_update, Unset):
            last_definition_update = UNSET
        else:
            last_definition_update = LastDefinitionUpdateAttribute.from_dict(_last_definition_update)

        attribute_object_endpoint_protection = cls(
            enabled=enabled,
            negate=negate,
            selected_vendors=selected_vendors,
            last_definition_update=last_definition_update,
        )

        attribute_object_endpoint_protection.additional_properties = d
        return attribute_object_endpoint_protection

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
