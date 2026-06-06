from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.certificate_dn import CertificateDN


T = TypeVar("T", bound="IssuerCertificate")


@_attrs_define
class IssuerCertificate:
    """
    Attributes:
        dn (CertificateDN):
        serial_number (str):
        raw (str):
    """

    dn: CertificateDN
    serial_number: str
    raw: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        dn = self.dn.to_dict()

        serial_number = self.serial_number

        raw = self.raw

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "DN": dn,
                "serialNumber": serial_number,
                "raw": raw,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.certificate_dn import CertificateDN

        d = dict(src_dict)
        dn = CertificateDN.from_dict(d.pop("DN"))

        serial_number = d.pop("serialNumber")

        raw = d.pop("raw")

        issuer_certificate = cls(
            dn=dn,
            serial_number=serial_number,
            raw=raw,
        )

        issuer_certificate.additional_properties = d
        return issuer_certificate

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
