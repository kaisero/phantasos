from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.dns_over_https_control_type_0_action import DnsOverHttpsControlType0Action
from ..models.dns_over_https_control_type_0_failure_mode import DnsOverHttpsControlType0FailureMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="DnsOverHttpsControlType0")


@_attrs_define
class DnsOverHttpsControlType0:
    """Set DNS resolving on top of the HTTPS protocol, for encrypting the requests and their resolutions. resolverUrl and
    adnsEnabled=true are mutually exclusive.

        Attributes:
            action (DnsOverHttpsControlType0Action): Whether DNS-over-HTTPS is enabled.
            failure_mode (DnsOverHttpsControlType0FailureMode | Unset): Upon DNS-over-HTTPS resolve failure. Required when
                action is 'enable'.
            resolver_url (str | Unset): DNS-over-HTTPS resolver URL. Applies when action is 'enable'.
    """

    action: DnsOverHttpsControlType0Action
    failure_mode: DnsOverHttpsControlType0FailureMode | Unset = UNSET
    resolver_url: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        failure_mode: str | Unset = UNSET
        if not isinstance(self.failure_mode, Unset):
            failure_mode = self.failure_mode.value

        resolver_url = self.resolver_url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if failure_mode is not UNSET:
            field_dict["failureMode"] = failure_mode
        if resolver_url is not UNSET:
            field_dict["resolverUrl"] = resolver_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = DnsOverHttpsControlType0Action(d.pop("action"))

        _failure_mode = d.pop("failureMode", UNSET)
        failure_mode: DnsOverHttpsControlType0FailureMode | Unset
        if isinstance(_failure_mode, Unset):
            failure_mode = UNSET
        else:
            failure_mode = DnsOverHttpsControlType0FailureMode(_failure_mode)

        resolver_url = d.pop("resolverUrl", UNSET)

        dns_over_https_control_type_0 = cls(
            action=action,
            failure_mode=failure_mode,
            resolver_url=resolver_url,
        )

        return dns_over_https_control_type_0
