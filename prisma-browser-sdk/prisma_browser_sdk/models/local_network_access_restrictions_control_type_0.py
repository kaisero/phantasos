from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.local_network_access_restrictions_control_type_0_action import (
    LocalNetworkAccessRestrictionsControlType0Action,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="LocalNetworkAccessRestrictionsControlType0")


@_attrs_define
class LocalNetworkAccessRestrictionsControlType0:
    """Manage website access to local network endpoints.

    Attributes:
        action (LocalNetworkAccessRestrictionsControlType0Action): Whether local network access is enabled.
        allow_list (list[str] | Unset): Auto Allow Local Network Access List.
        block_list (list[str] | Unset): Block Local Network Access List.
    """

    action: LocalNetworkAccessRestrictionsControlType0Action
    allow_list: list[str] | Unset = UNSET
    block_list: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        allow_list: list[str] | Unset = UNSET
        if not isinstance(self.allow_list, Unset):
            allow_list = self.allow_list

        block_list: list[str] | Unset = UNSET
        if not isinstance(self.block_list, Unset):
            block_list = self.block_list

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if allow_list is not UNSET:
            field_dict["allowList"] = allow_list
        if block_list is not UNSET:
            field_dict["blockList"] = block_list

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = LocalNetworkAccessRestrictionsControlType0Action(d.pop("action"))

        allow_list = cast(list[str], d.pop("allowList", UNSET))

        block_list = cast(list[str], d.pop("blockList", UNSET))

        local_network_access_restrictions_control_type_0 = cls(
            action=action,
            allow_list=allow_list,
            block_list=block_list,
        )

        return local_network_access_restrictions_control_type_0
