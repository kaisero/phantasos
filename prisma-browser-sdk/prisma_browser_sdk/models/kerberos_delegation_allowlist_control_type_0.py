from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.kerberos_delegation_allowlist_control_type_0_action import KerberosDelegationAllowlistControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="KerberosDelegationAllowlistControlType0")


@_attrs_define
class KerberosDelegationAllowlistControlType0:
    """List the hosts that may forward a user's Kerberos ticket to downstream services.

    Attributes:
        action (KerberosDelegationAllowlistControlType0Action): Whether to allow or block Kerberos Delegation Allowlist.
        included_domains (list[str] | Unset): Include specific domains.
    """

    action: KerberosDelegationAllowlistControlType0Action
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
        action = KerberosDelegationAllowlistControlType0Action(d.pop("action"))

        included_domains = cast(list[str], d.pop("includedDomains", UNSET))

        kerberos_delegation_allowlist_control_type_0 = cls(
            action=action,
            included_domains=included_domains,
        )

        return kerberos_delegation_allowlist_control_type_0
