from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PostScopeUsers")


@_attrs_define
class PostScopeUsers:
    """The users or user groups the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any users or user groups are included in the scope. If isAny is
            set to true, no other fields should be present, and all users and user groups will be included in the scope. If
            isAny is set to false, the final scope must contain at least one user or user group.
        users (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
        user_groups (list[str] | None | Unset): A collection of up to 1000 unique Pulid strings.
    """

    is_any: bool | None | Unset = UNSET
    users: list[str] | None | Unset = UNSET
    user_groups: list[str] | None | Unset = UNSET

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

        user_groups: list[str] | None | Unset
        if isinstance(self.user_groups, Unset):
            user_groups = UNSET
        elif isinstance(self.user_groups, list):
            user_groups = self.user_groups

        else:
            user_groups = self.user_groups

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if users is not UNSET:
            field_dict["users"] = users
        if user_groups is not UNSET:
            field_dict["userGroups"] = user_groups

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

        post_scope_users = cls(
            is_any=is_any,
            users=users,
            user_groups=user_groups,
        )

        return post_scope_users
