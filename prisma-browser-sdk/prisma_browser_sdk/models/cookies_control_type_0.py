from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.cookies_control_type_0_action import CookiesControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="CookiesControlType0")


@_attrs_define
class CookiesControlType0:
    """Control the ability to store cookies on the browser.

    Attributes:
        action (CookiesControlType0Action): Cookies action.
        excluded_domains (list[str] | Unset): Domains excluded from the chosen action. Only supported when action is
            allow or block.
        included_domains (list[str] | Unset): Domains to include for session-only cookie storage. Only supported when
            action is clearOnSessionEnd.
    """

    action: CookiesControlType0Action
    excluded_domains: list[str] | Unset = UNSET
    included_domains: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        excluded_domains: list[str] | Unset = UNSET
        if not isinstance(self.excluded_domains, Unset):
            excluded_domains = self.excluded_domains

        included_domains: list[str] | Unset = UNSET
        if not isinstance(self.included_domains, Unset):
            included_domains = self.included_domains

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if excluded_domains is not UNSET:
            field_dict["excludedDomains"] = excluded_domains
        if included_domains is not UNSET:
            field_dict["includedDomains"] = included_domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = CookiesControlType0Action(d.pop("action"))

        excluded_domains = cast(list[str], d.pop("excludedDomains", UNSET))

        included_domains = cast(list[str], d.pop("includedDomains", UNSET))

        cookies_control_type_0 = cls(
            action=action,
            excluded_domains=excluded_domains,
            included_domains=included_domains,
        )

        return cookies_control_type_0
