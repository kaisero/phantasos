from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.allow_block_control_type_0_action import AllowBlockControlType0Action

T = TypeVar("T", bound="AllowBlockControlType0")


@_attrs_define
class AllowBlockControlType0:
    """A simple control with an allow or block action. Re-usable by any data control that only needs a binary allow/block
    decision.

        Attributes:
            action (AllowBlockControlType0Action): The action for this control.
    """

    action: AllowBlockControlType0Action

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = AllowBlockControlType0Action(d.pop("action"))

        allow_block_control_type_0 = cls(
            action=action,
        )

        return allow_block_control_type_0
