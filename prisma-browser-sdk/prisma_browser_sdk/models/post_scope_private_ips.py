from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PostScopePrivateIps")


@_attrs_define
class PostScopePrivateIps:
    """The private IP addresses the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any private IP addresses are included in the scope. If isAny is
            set to true, no other fields should be present, and all private IP addresses will be included in the scope. If
            isAny is set to false, the final scope must contain at least one private IP.
        private_ips (list[str] | None | Unset):
    """

    is_any: bool | None | Unset = UNSET
    private_ips: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        is_any: bool | None | Unset
        if isinstance(self.is_any, Unset):
            is_any = UNSET
        else:
            is_any = self.is_any

        private_ips: list[str] | None | Unset
        if isinstance(self.private_ips, Unset):
            private_ips = UNSET
        elif isinstance(self.private_ips, list):
            private_ips = self.private_ips

        else:
            private_ips = self.private_ips

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if private_ips is not UNSET:
            field_dict["privateIps"] = private_ips

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_is_any(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        is_any = _parse_is_any(d.pop("isAny", UNSET))

        def _parse_private_ips(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_ip_array_type_0 = cast(list[str], data)

                return componentsschemas_ip_array_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None | Unset, data)

        private_ips = _parse_private_ips(d.pop("privateIps", UNSET))

        post_scope_private_ips = cls(
            is_any=is_any,
            private_ips=private_ips,
        )

        return post_scope_private_ips
