from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.update_user_group_body_users_item_action import UpdateUserGroupBodyUsersItemAction

T = TypeVar("T", bound="UpdateUserGroupBodyUsersItem")


@_attrs_define
class UpdateUserGroupBodyUsersItem:
    """
    Attributes:
        user_id (str): User ID
        action (UpdateUserGroupBodyUsersItemAction): Action to perform (add or remove the user)
    """

    user_id: str
    action: UpdateUserGroupBodyUsersItemAction
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        user_id = self.user_id

        action = self.action.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "userId": user_id,
                "action": action,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        user_id = d.pop("userId")

        action = UpdateUserGroupBodyUsersItemAction(d.pop("action"))

        update_user_group_body_users_item = cls(
            user_id=user_id,
            action=action,
        )

        update_user_group_body_users_item.additional_properties = d
        return update_user_group_body_users_item

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
