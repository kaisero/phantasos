from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CertificateDN")


@_attrs_define
class CertificateDN:
    """
    Attributes:
        cn (str | Unset):
        o (str | Unset):
        ou (str | Unset):
        l (str | Unset):
    """

    cn: str | Unset = UNSET
    o: str | Unset = UNSET
    ou: str | Unset = UNSET
    l: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cn = self.cn

        o = self.o

        ou = self.ou

        l = self.l

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if cn is not UNSET:
            field_dict["CN"] = cn
        if o is not UNSET:
            field_dict["O"] = o
        if ou is not UNSET:
            field_dict["OU"] = ou
        if l is not UNSET:
            field_dict["L"] = l

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        cn = d.pop("CN", UNSET)

        o = d.pop("O", UNSET)

        ou = d.pop("OU", UNSET)

        l = d.pop("L", UNSET)

        certificate_dn = cls(
            cn=cn,
            o=o,
            ou=ou,
            l=l,
        )

        certificate_dn.additional_properties = d
        return certificate_dn

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
