from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.browser_history_control_type_0_action import BrowserHistoryControlType0Action

T = TypeVar("T", bound="BrowserHistoryControlType0")


@_attrs_define
class BrowserHistoryControlType0:
    """Control the ability to delete history from the browser.

    Attributes:
        action (BrowserHistoryControlType0Action): Browser History action.
    """

    action: BrowserHistoryControlType0Action

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
        action = BrowserHistoryControlType0Action(d.pop("action"))

        browser_history_control_type_0 = cls(
            action=action,
        )

        return browser_history_control_type_0
