from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.session_refresh_control_type_0_action import SessionRefreshControlType0Action
from ..models.session_refresh_control_type_0_max_session_duration import SessionRefreshControlType0MaxSessionDuration
from ..types import UNSET, Unset

T = TypeVar("T", bound="SessionRefreshControlType0")


@_attrs_define
class SessionRefreshControlType0:
    """Periodically require the user to re-authenticate.

    Attributes:
        action (SessionRefreshControlType0Action): Whether Session Refresh is enabled.
        max_session_duration (SessionRefreshControlType0MaxSessionDuration | Unset): Maximum session duration before the
            user must re-authenticate. Applies when action is 'enable'. Defaults to '7days'.
        on_browser_closed (bool | Unset): Whether to require re-authentication when the browser is closed. Applies when
            action is 'enable'.
    """

    action: SessionRefreshControlType0Action
    max_session_duration: SessionRefreshControlType0MaxSessionDuration | Unset = UNSET
    on_browser_closed: bool | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        max_session_duration: str | Unset = UNSET
        if not isinstance(self.max_session_duration, Unset):
            max_session_duration = self.max_session_duration.value

        on_browser_closed = self.on_browser_closed

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if max_session_duration is not UNSET:
            field_dict["maxSessionDuration"] = max_session_duration
        if on_browser_closed is not UNSET:
            field_dict["onBrowserClosed"] = on_browser_closed

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = SessionRefreshControlType0Action(d.pop("action"))

        _max_session_duration = d.pop("maxSessionDuration", UNSET)
        max_session_duration: SessionRefreshControlType0MaxSessionDuration | Unset
        if isinstance(_max_session_duration, Unset):
            max_session_duration = UNSET
        else:
            max_session_duration = SessionRefreshControlType0MaxSessionDuration(_max_session_duration)

        on_browser_closed = d.pop("onBrowserClosed", UNSET)

        session_refresh_control_type_0 = cls(
            action=action,
            max_session_duration=max_session_duration,
            on_browser_closed=on_browser_closed,
        )

        return session_refresh_control_type_0
