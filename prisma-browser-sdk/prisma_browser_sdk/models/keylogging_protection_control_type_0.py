from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.keylogging_protection_control_type_0_action import KeyloggingProtectionControlType0Action

T = TypeVar("T", bound="KeyloggingProtectionControlType0")


@_attrs_define
class KeyloggingProtectionControlType0:
    """Prevent keyloggers from capturing user input while using the browser (Windows only).

    Attributes:
        action (KeyloggingProtectionControlType0Action): Whether Keylogging Protection is enabled.
    """

    action: KeyloggingProtectionControlType0Action

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
        action = KeyloggingProtectionControlType0Action(d.pop("action"))

        keylogging_protection_control_type_0 = cls(
            action=action,
        )

        return keylogging_protection_control_type_0
