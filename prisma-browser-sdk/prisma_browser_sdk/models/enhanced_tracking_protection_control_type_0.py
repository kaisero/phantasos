from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.enhanced_tracking_protection_control_type_0_action import EnhancedTrackingProtectionControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="EnhancedTrackingProtectionControlType0")


@_attrs_define
class EnhancedTrackingProtectionControlType0:
    """Manage tracking protection and cross-site tracking.

    Attributes:
        action (EnhancedTrackingProtectionControlType0Action): Whether Enhanced Tracking Protection is enabled.
        exclude_domains (list[str] | Unset): List of excluded domains.
    """

    action: EnhancedTrackingProtectionControlType0Action
    exclude_domains: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        exclude_domains: list[str] | Unset = UNSET
        if not isinstance(self.exclude_domains, Unset):
            exclude_domains = self.exclude_domains

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if exclude_domains is not UNSET:
            field_dict["excludeDomains"] = exclude_domains

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = EnhancedTrackingProtectionControlType0Action(d.pop("action"))

        exclude_domains = cast(list[str], d.pop("excludeDomains", UNSET))

        enhanced_tracking_protection_control_type_0 = cls(
            action=action,
            exclude_domains=exclude_domains,
        )

        return enhanced_tracking_protection_control_type_0
