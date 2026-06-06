from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.locations import Locations

T = TypeVar("T", bound="GetScopeLocations")


@_attrs_define
class GetScopeLocations:
    """The locations the rule applies to.

    Attributes:
        is_any (bool): Flag indicating if any locations are included in the scope.
        locations (list[Locations]): Geographical locations to which the rule applies.
    """

    is_any: bool
    locations: list[Locations]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_any = self.is_any

        locations = []
        for locations_item_data in self.locations:
            locations_item = locations_item_data.value
            locations.append(locations_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "isAny": is_any,
                "locations": locations,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        is_any = d.pop("isAny")

        locations = []
        _locations = d.pop("locations")
        for locations_item_data in _locations:
            locations_item = Locations(locations_item_data)

            locations.append(locations_item)

        get_scope_locations = cls(
            is_any=is_any,
            locations=locations,
        )

        get_scope_locations.additional_properties = d
        return get_scope_locations

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
