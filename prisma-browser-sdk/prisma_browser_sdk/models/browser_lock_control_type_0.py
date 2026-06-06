from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.browser_lock_control_type_0_action import BrowserLockControlType0Action
from ..models.browser_lock_control_type_0_idle_timeout_minutes import BrowserLockControlType0IdleTimeoutMinutes
from ..types import UNSET, Unset

T = TypeVar("T", bound="BrowserLockControlType0")


@_attrs_define
class BrowserLockControlType0:
    """Require the user to unlock their browser.

    Attributes:
        action (BrowserLockControlType0Action): Whether Browser Lock is enabled.
        idle_timeout_minutes (BrowserLockControlType0IdleTimeoutMinutes | Unset): Time the user can be idle before the
            browser locks. Use 0 for never. Applies when action is 'enable'. Defaults to 0.
    """

    action: BrowserLockControlType0Action
    idle_timeout_minutes: BrowserLockControlType0IdleTimeoutMinutes | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        idle_timeout_minutes: int | Unset = UNSET
        if not isinstance(self.idle_timeout_minutes, Unset):
            idle_timeout_minutes = self.idle_timeout_minutes.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if idle_timeout_minutes is not UNSET:
            field_dict["idleTimeoutMinutes"] = idle_timeout_minutes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = BrowserLockControlType0Action(d.pop("action"))

        _idle_timeout_minutes = d.pop("idleTimeoutMinutes", UNSET)
        idle_timeout_minutes: BrowserLockControlType0IdleTimeoutMinutes | Unset
        if isinstance(_idle_timeout_minutes, Unset):
            idle_timeout_minutes = UNSET
        else:
            idle_timeout_minutes = BrowserLockControlType0IdleTimeoutMinutes(_idle_timeout_minutes)

        browser_lock_control_type_0 = cls(
            action=action,
            idle_timeout_minutes=idle_timeout_minutes,
        )

        return browser_lock_control_type_0
