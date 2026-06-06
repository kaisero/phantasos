from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PatchScopeUsers")


@_attrs_define
class PatchScopeUsers:
    """The users or user groups the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any users or user groups are included in the scope. If isAny is
            set to true, no other fields should be present, and all users and user groups will be included in the scope. If
            isAny is set to false, the final scope must contain at least one user or user group.
        users (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        add_users (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        remove_users (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        user_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        add_user_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        remove_user_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
    """

    is_any: bool | None | Unset = UNSET
    users: list[str] | None | Unset = UNSET
    add_users: list[str] | None | Unset = UNSET
    remove_users: list[str] | None | Unset = UNSET
    user_groups: list[str] | None | Unset = UNSET
    add_user_groups: list[str] | None | Unset = UNSET
    remove_user_groups: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        is_any: bool | None | Unset
        if isinstance(self.is_any, Unset):
            is_any = UNSET
        else:
            is_any = self.is_any

        users: list[str] | None | Unset
        if isinstance(self.users, Unset):
            users = UNSET
        elif isinstance(self.users, list):
            users = self.users

        else:
            users = self.users

        add_users: list[str] | None | Unset
        if isinstance(self.add_users, Unset):
            add_users = UNSET
        elif isinstance(self.add_users, list):
            add_users = self.add_users

        else:
            add_users = self.add_users

        remove_users: list[str] | None | Unset
        if isinstance(self.remove_users, Unset):
            remove_users = UNSET
        elif isinstance(self.remove_users, list):
            remove_users = self.remove_users

        else:
            remove_users = self.remove_users

        user_groups: list[str] | None | Unset
        if isinstance(self.user_groups, Unset):
            user_groups = UNSET
        elif isinstance(self.user_groups, list):
            user_groups = self.user_groups

        else:
            user_groups = self.user_groups

        add_user_groups: list[str] | None | Unset
        if isinstance(self.add_user_groups, Unset):
            add_user_groups = UNSET
        elif isinstance(self.add_user_groups, list):
            add_user_groups = self.add_user_groups

        else:
            add_user_groups = self.add_user_groups

        remove_user_groups: list[str] | None | Unset
        if isinstance(self.remove_user_groups, Unset):
            remove_user_groups = UNSET
        elif isinstance(self.remove_user_groups, list):
            remove_user_groups = self.remove_user_groups

        else:
            remove_user_groups = self.remove_user_groups

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if users is not UNSET:
            field_dict["users"] = users
        if add_users is not UNSET:
            field_dict["addUsers"] = add_users
        if remove_users is not UNSET:
            field_dict["removeUsers"] = remove_users
        if user_groups is not UNSET:
            field_dict["userGroups"] = user_groups
        if add_user_groups is not UNSET:
            field_dict["addUserGroups"] = add_user_groups
        if remove_user_groups is not UNSET:
            field_dict["removeUserGroups"] = remove_user_groups

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

        def _parse_users(data: object) -> list[str] | None | Unset:
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

        users = _parse_users(d.pop("users", UNSET))

        def _parse_add_users(data: object) -> list[str] | None | Unset:
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

        add_users = _parse_add_users(d.pop("addUsers", UNSET))

        def _parse_remove_users(data: object) -> list[str] | None | Unset:
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

        remove_users = _parse_remove_users(d.pop("removeUsers", UNSET))

        def _parse_user_groups(data: object) -> list[str] | None | Unset:
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

        user_groups = _parse_user_groups(d.pop("userGroups", UNSET))

        def _parse_add_user_groups(data: object) -> list[str] | None | Unset:
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

        add_user_groups = _parse_add_user_groups(d.pop("addUserGroups", UNSET))

        def _parse_remove_user_groups(data: object) -> list[str] | None | Unset:
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

        remove_user_groups = _parse_remove_user_groups(d.pop("removeUserGroups", UNSET))

        patch_scope_users = cls(
            is_any=is_any,
            users=users,
            add_users=add_users,
            remove_users=remove_users,
            user_groups=user_groups,
            add_user_groups=add_user_groups,
            remove_user_groups=remove_user_groups,
        )

        return patch_scope_users
