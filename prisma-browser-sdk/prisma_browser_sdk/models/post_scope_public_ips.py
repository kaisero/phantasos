from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="PostScopePublicIps")


@_attrs_define
class PostScopePublicIps:
    """The public IP addresses the rule applies to.

    Attributes:
        is_any (bool | None | Unset): Flag indicating if any public IP addresses are included in the scope. If isAny is
            set to true, no other fields should be present, and all public IP addresses will be included in the scope. If
            isAny is set to false, the final scope must contain at least one public IP.
        public_ips (list[str] | None | Unset):
    """

    is_any: bool | None | Unset = UNSET
    public_ips: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        is_any: bool | None | Unset
        if isinstance(self.is_any, Unset):
            is_any = UNSET
        else:
            is_any = self.is_any

        public_ips: list[str] | None | Unset
        if isinstance(self.public_ips, Unset):
            public_ips = UNSET
        elif isinstance(self.public_ips, list):
            public_ips = self.public_ips

        else:
            public_ips = self.public_ips

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if is_any is not UNSET:
            field_dict["isAny"] = is_any
        if public_ips is not UNSET:
            field_dict["publicIps"] = public_ips

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

        def _parse_public_ips(data: object) -> list[str] | None | Unset:
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

        public_ips = _parse_public_ips(d.pop("publicIps", UNSET))

        post_scope_public_ips = cls(
            is_any=is_any,
            public_ips=public_ips,
        )

        return post_scope_public_ips
