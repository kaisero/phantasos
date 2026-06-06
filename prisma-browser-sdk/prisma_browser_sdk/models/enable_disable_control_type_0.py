from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.enable_disable_control_type_0_action import EnableDisableControlType0Action

T = TypeVar("T", bound="EnableDisableControlType0")


@_attrs_define
class EnableDisableControlType0:
    """A simple control with an enable or disable action. Re-usable by any control that only needs a binary enable/disable
    decision.

        Attributes:
            action (EnableDisableControlType0Action): The action for this control.
    """

    action: EnableDisableControlType0Action

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
        action = EnableDisableControlType0Action(d.pop("action"))

        enable_disable_control_type_0 = cls(
            action=action,
        )

        return enable_disable_control_type_0
