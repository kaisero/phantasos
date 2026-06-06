from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="GetScopePublicIps")


@_attrs_define
class GetScopePublicIps:
    """The public IP addresses the rule applies to.

    Attributes:
        is_any (bool): Flag indicating if any public IP addresses are included in the scope.
        public_ips (list[str] | None): Public IP addresses affected by the rule.
    """

    is_any: bool
    public_ips: list[str] | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_any = self.is_any

        public_ips: list[str] | None
        if isinstance(self.public_ips, list):
            public_ips = self.public_ips

        else:
            public_ips = self.public_ips

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "isAny": is_any,
                "publicIps": public_ips,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        is_any = d.pop("isAny")

        def _parse_public_ips(data: object) -> list[str] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                public_ips_type_0 = cast(list[str], data)

                return public_ips_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None, data)

        public_ips = _parse_public_ips(d.pop("publicIps"))

        get_scope_public_ips = cls(
            is_any=is_any,
            public_ips=public_ips,
        )

        get_scope_public_ips.additional_properties = d
        return get_scope_public_ips

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
