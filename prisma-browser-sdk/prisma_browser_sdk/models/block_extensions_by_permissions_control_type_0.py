from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.block_extensions_by_permissions_control_type_0_action import (
    BlockExtensionsByPermissionsControlType0Action,
)
from ..models.block_extensions_by_permissions_control_type_0_blocked_permissions_item import (
    BlockExtensionsByPermissionsControlType0BlockedPermissionsItem,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="BlockExtensionsByPermissionsControlType0")


@_attrs_define
class BlockExtensionsByPermissionsControlType0:
    """Prevent users from running extensions that require certain permissions.

    Attributes:
        action (BlockExtensionsByPermissionsControlType0Action): Whether to grant all permissions or block extensions
            that use specific permissions.
        blocked_permissions (list[BlockExtensionsByPermissionsControlType0BlockedPermissionsItem] | Unset): Chrome
            extension permissions to block.
    """

    action: BlockExtensionsByPermissionsControlType0Action
    blocked_permissions: list[BlockExtensionsByPermissionsControlType0BlockedPermissionsItem] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        blocked_permissions: list[str] | Unset = UNSET
        if not isinstance(self.blocked_permissions, Unset):
            blocked_permissions = []
            for blocked_permissions_item_data in self.blocked_permissions:
                blocked_permissions_item = blocked_permissions_item_data.value
                blocked_permissions.append(blocked_permissions_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if blocked_permissions is not UNSET:
            field_dict["blockedPermissions"] = blocked_permissions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = BlockExtensionsByPermissionsControlType0Action(d.pop("action"))

        _blocked_permissions = d.pop("blockedPermissions", UNSET)
        blocked_permissions: list[BlockExtensionsByPermissionsControlType0BlockedPermissionsItem] | Unset = UNSET
        if _blocked_permissions is not UNSET:
            blocked_permissions = []
            for blocked_permissions_item_data in _blocked_permissions:
                blocked_permissions_item = BlockExtensionsByPermissionsControlType0BlockedPermissionsItem(
                    blocked_permissions_item_data
                )

                blocked_permissions.append(blocked_permissions_item)

        block_extensions_by_permissions_control_type_0 = cls(
            action=action,
            blocked_permissions=blocked_permissions,
        )

        return block_extensions_by_permissions_control_type_0
