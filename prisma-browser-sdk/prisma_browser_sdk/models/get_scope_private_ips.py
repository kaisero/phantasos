from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="GetScopePrivateIps")


@_attrs_define
class GetScopePrivateIps:
    """The private IP addresses the rule applies to.

    Attributes:
        is_any (bool): Flag indicating if any private IP addresses are included in the scope.
        private_ips (list[str] | None): Private IP addresses affected by the rule.
    """

    is_any: bool
    private_ips: list[str] | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        is_any = self.is_any

        private_ips: list[str] | None
        if isinstance(self.private_ips, list):
            private_ips = self.private_ips

        else:
            private_ips = self.private_ips

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "isAny": is_any,
                "privateIps": private_ips,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        is_any = d.pop("isAny")

        def _parse_private_ips(data: object) -> list[str] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                private_ips_type_0 = cast(list[str], data)

                return private_ips_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[str] | None, data)

        private_ips = _parse_private_ips(d.pop("privateIps"))

        get_scope_private_ips = cls(
            is_any=is_any,
            private_ips=private_ips,
        )

        get_scope_private_ips.additional_properties = d
        return get_scope_private_ips

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
