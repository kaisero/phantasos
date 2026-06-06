from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.authentication_server_allowlist_control_type_0_action import (
    AuthenticationServerAllowlistControlType0Action,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="AuthenticationServerAllowlistControlType0")


@_attrs_define
class AuthenticationServerAllowlistControlType0:
    """List the servers allowed to use Integrated Authentication.

    Attributes:
        action (AuthenticationServerAllowlistControlType0Action): Whether to set an authentication server allowlist or
            unset it.
        included_domains (list[str] | Unset): Servers allowed to use Integrated Authentication.
    """

    action: AuthenticationServerAllowlistControlType0Action
    included_domains: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        included_domains: list[str] | Unset = UNSET
        if not isinstance(self.included_domains, Unset):
            included_domains = self.included_domains

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if included_domains is not UNSET:
            field_dict["includedDomains"] = included_domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = AuthenticationServerAllowlistControlType0Action(d.pop("action"))

        included_domains = cast(list[str], d.pop("includedDomains", UNSET))

        authentication_server_allowlist_control_type_0 = cls(
            action=action,
            included_domains=included_domains,
        )

        return authentication_server_allowlist_control_type_0
