from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchScopeDeviceGroups")


@_attrs_define
class PatchScopeDeviceGroups:
    """The device groups the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any device groups are included in the scope. If isAny is set to
            true, no other fields should be present, and all device groups will be included in the scope. If isAny is set to
            false, the final scope must contain at least one device group.
        device_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        add_device_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        remove_device_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
    """

    is_any: bool | None | Unset = UNSET
    device_groups: list[str] | None | Unset = UNSET
    add_device_groups: list[str] | None | Unset = UNSET
    remove_device_groups: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        is_any: bool | None | Unset
        if isinstance(self.is_any, Unset):
            is_any = UNSET
        else:
            is_any = self.is_any

        device_groups: list[str] | None | Unset
        if isinstance(self.device_groups, Unset):
            device_groups = UNSET
        elif isinstance(self.device_groups, list):
            device_groups = self.device_groups

        else:
            device_groups = self.device_groups

        add_device_groups: list[str] | None | Unset
        if isinstance(self.add_device_groups, Unset):
            add_device_groups = UNSET
        elif isinstance(self.add_device_groups, list):
            add_device_groups = self.add_device_groups

        else:
            add_device_groups = self.add_device_groups

        remove_device_groups: list[str] | None | Unset
        if isinstance(self.remove_device_groups, Unset):
            remove_device_groups = UNSET
        elif isinstance(self.remove_device_groups, list):
            remove_device_groups = self.remove_device_groups

        else:
            remove_device_groups = self.remove_device_groups

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if device_groups is not UNSET:
            field_dict["deviceGroups"] = device_groups
        if add_device_groups is not UNSET:
            field_dict["addDeviceGroups"] = add_device_groups
        if remove_device_groups is not UNSET:
            field_dict["removeDeviceGroups"] = remove_device_groups

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

        def _parse_device_groups(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_pulid_array_type_0 = cast(list[str], data)

                return componentsschemas_pulid_array_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        device_groups = _parse_device_groups(d.pop("deviceGroups", UNSET))

        def _parse_add_device_groups(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_pulid_array_type_0 = cast(list[str], data)

                return componentsschemas_pulid_array_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        add_device_groups = _parse_add_device_groups(d.pop("addDeviceGroups", UNSET))

        def _parse_remove_device_groups(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_pulid_array_type_0 = cast(list[str], data)

                return componentsschemas_pulid_array_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        remove_device_groups = _parse_remove_device_groups(d.pop("removeDeviceGroups", UNSET))

        patch_scope_device_groups = cls(
            is_any=is_any,
            device_groups=device_groups,
            add_device_groups=add_device_groups,
            remove_device_groups=remove_device_groups,
        )

        return patch_scope_device_groups
