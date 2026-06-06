from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.locations import Locations
from ..types import UNSET, Unset

T = TypeVar("T", bound="PostScopeLocations")


@_attrs_define
class PostScopeLocations:
    """The locations the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any locations are included in the scope. If isAny is set to
            true, no other fields should be present, and all locations will be included in the scope. If isAny is set to
            false, the final scope must contain at least one location.
        locations (list[Locations] | None | Unset):
    """

    is_any: bool | None | Unset = UNSET
    locations: list[Locations] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        is_any: bool | None | Unset
        if isinstance(self.is_any, Unset):
            is_any = UNSET
        else:
            is_any = self.is_any

        locations: list[str] | None | Unset
        if isinstance(self.locations, Unset):
            locations = UNSET
        elif isinstance(self.locations, list):
            locations = []
            for componentsschemas_country_code_array_type_0_item_data in self.locations:
                componentsschemas_country_code_array_type_0_item = (
                    componentsschemas_country_code_array_type_0_item_data.value
                )
                locations.append(componentsschemas_country_code_array_type_0_item)

        else:
            locations = self.locations

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if locations is not UNSET:
            field_dict["locations"] = locations

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_is_any(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        is_any = _parse_is_any(d.pop("isAny", UNSET))

        def _parse_locations(data: object) -> list[Locations] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_country_code_array_type_0 = []
                _componentsschemas_country_code_array_type_0 = data
                for (
                    componentsschemas_country_code_array_type_0_item_data
                ) in _componentsschemas_country_code_array_type_0:
                    componentsschemas_country_code_array_type_0_item = Locations(
                        componentsschemas_country_code_array_type_0_item_data
                    )

                    componentsschemas_country_code_array_type_0.append(componentsschemas_country_code_array_type_0_item)

                return componentsschemas_country_code_array_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[Locations] | None | Unset, data)

        locations = _parse_locations(d.pop("locations", UNSET))

        post_scope_locations = cls(
            is_any=is_any,
            locations=locations,
        )

        return post_scope_locations
