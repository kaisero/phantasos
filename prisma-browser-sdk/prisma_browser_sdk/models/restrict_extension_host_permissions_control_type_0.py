from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.restrict_extension_host_permissions_control_type_0_action import (
    RestrictExtensionHostPermissionsControlType0Action,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="RestrictExtensionHostPermissionsControlType0")


@_attrs_define
class RestrictExtensionHostPermissionsControlType0:
    """Prevent extensions from running scripts and accessing content in websites.

    Attributes:
        action (RestrictExtensionHostPermissionsControlType0Action): Whether to restrict extension host permissions on
            all domains, specific domains, or disable the restriction.
        included_domains (list[str] | Unset): Domains where extension host permissions are restricted.
    """

    action: RestrictExtensionHostPermissionsControlType0Action
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
        action = RestrictExtensionHostPermissionsControlType0Action(d.pop("action"))

        included_domains = cast(list[str], d.pop("includedDomains", UNSET))

        restrict_extension_host_permissions_control_type_0 = cls(
            action=action,
            included_domains=included_domains,
        )

        return restrict_extension_host_permissions_control_type_0
