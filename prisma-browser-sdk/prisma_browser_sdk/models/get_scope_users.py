from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.user_group_ref import UserGroupRef
    from ..models.user_ref import UserRef


T = TypeVar("T", bound="GetScopeUsers")


@_attrs_define
class GetScopeUsers:
    """The users or user groups the rule applies to.

    Attributes:
        is_any (bool): Flag indicating if any users or user groups are included in the scope.
        users (list[UserRef]): Users the rule applies to. [] = any user, [{id, name, email}] = specific users
        user_groups (list[UserGroupRef]): User groups the rule applies to. [] = any group, [{id, name}] = specific
            groups
    """

    is_any: bool
    users: list[UserRef]
    user_groups: list[UserGroupRef]
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_any = self.is_any

        users = []
        for users_item_data in self.users:
            users_item = users_item_data.to_dict()
            users.append(users_item)

        user_groups = []
        for user_groups_item_data in self.user_groups:
            user_groups_item = user_groups_item_data.to_dict()
            user_groups.append(user_groups_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "isAny": is_any,
                "users": users,
                "userGroups": user_groups,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user_group_ref import UserGroupRef
        from ..models.user_ref import UserRef

        d = dict(src_dict)
        is_any = d.pop("isAny")

        users = []
        _users = d.pop("users")
        for users_item_data in _users:
            users_item = UserRef.from_dict(users_item_data)

            users.append(users_item)

        user_groups = []
        _user_groups = d.pop("userGroups")
        for user_groups_item_data in _user_groups:
            user_groups_item = UserGroupRef.from_dict(user_groups_item_data)

            user_groups.append(user_groups_item)

        get_scope_users = cls(
            is_any=is_any,
            users=users,
            user_groups=user_groups,
        )

        get_scope_users.additional_properties = d
        return get_scope_users

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
