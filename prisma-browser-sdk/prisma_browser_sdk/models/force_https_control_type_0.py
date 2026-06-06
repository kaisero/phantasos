from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.force_https_control_type_0_action import ForceHttpsControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="ForceHttpsControlType0")


@_attrs_define
class ForceHttpsControlType0:
    """Force using HTTPS instead of HTTP to reduce the risk of MitM attacks and sending sensitive information in cleartext.

    Attributes:
        action (ForceHttpsControlType0Action): Whether Force HTTPS is enabled.
        excluded_domains (list[str] | Unset): Domains excluded from forced HTTPS.
        block_bypass (bool | Unset): When true, users cannot bypass the HTTPS enforcement warning page. Requires feature
            enablement per tenant.
    """

    action: ForceHttpsControlType0Action
    excluded_domains: list[str] | Unset = UNSET
    block_bypass: bool | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        excluded_domains: list[str] | Unset = UNSET
        if not isinstance(self.excluded_domains, Unset):
            excluded_domains = self.excluded_domains

        block_bypass = self.block_bypass

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if excluded_domains is not UNSET:
            field_dict["excludedDomains"] = excluded_domains
        if block_bypass is not UNSET:
            field_dict["blockBypass"] = block_bypass

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = ForceHttpsControlType0Action(d.pop("action"))

        excluded_domains = cast(list[str], d.pop("excludedDomains", UNSET))

        block_bypass = d.pop("blockBypass", UNSET)

        force_https_control_type_0 = cls(
            action=action,
            excluded_domains=excluded_domains,
            block_bypass=block_bypass,
        )

        return force_https_control_type_0
