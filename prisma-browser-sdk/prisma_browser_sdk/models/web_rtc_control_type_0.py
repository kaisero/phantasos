from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.web_rtc_control_type_0_action import WebRtcControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="WebRtcControlType0")


@_attrs_define
class WebRtcControlType0:
    """Control the use of WebRTC mechanism, which might be exploited. Disabling it might impact the usability of websites
    working with WebRTC functionalities, like call/video streaming.

        Attributes:
            action (WebRtcControlType0Action): Whether to allow or block WebRTC.
            excluded_domains (list[str] | Unset): Domains excluded from the block action.
    """

    action: WebRtcControlType0Action
    excluded_domains: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        excluded_domains: list[str] | Unset = UNSET
        if not isinstance(self.excluded_domains, Unset):
            excluded_domains = self.excluded_domains

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if excluded_domains is not UNSET:
            field_dict["excludedDomains"] = excluded_domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = WebRtcControlType0Action(d.pop("action"))

        excluded_domains = cast(list[str], d.pop("excludedDomains", UNSET))

        web_rtc_control_type_0 = cls(
            action=action,
            excluded_domains=excluded_domains,
        )

        return web_rtc_control_type_0
