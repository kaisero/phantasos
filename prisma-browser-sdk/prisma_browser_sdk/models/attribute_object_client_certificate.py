from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issuer_certificate import IssuerCertificate


T = TypeVar("T", bound="AttributeObjectClientCertificate")


@_attrs_define
class AttributeObjectClientCertificate:
    """Check if the device's client certificate is signed by the provided issuer certificate

    Attributes:
        enabled (bool):
        negate (bool | Unset):  Default: False.
        issuer_certificates (list[IssuerCertificate] | Unset): List of trusted issuer certificates to validate against
    """

    enabled: bool
    negate: bool | Unset = False
    issuer_certificates: list[IssuerCertificate] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        issuer_certificates: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.issuer_certificates, Unset):
            issuer_certificates = []
            for issuer_certificates_item_data in self.issuer_certificates:
                issuer_certificates_item = issuer_certificates_item_data.to_dict()
                issuer_certificates.append(issuer_certificates_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if issuer_certificates is not UNSET:
            field_dict["issuerCertificates"] = issuer_certificates

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.issuer_certificate import IssuerCertificate

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _issuer_certificates = d.pop("issuerCertificates", UNSET)
        issuer_certificates: list[IssuerCertificate] | Unset = UNSET
        if _issuer_certificates is not UNSET:
            issuer_certificates = []
            for issuer_certificates_item_data in _issuer_certificates:
                issuer_certificates_item = IssuerCertificate.from_dict(issuer_certificates_item_data)

                issuer_certificates.append(issuer_certificates_item)

        attribute_object_client_certificate = cls(
            enabled=enabled,
            negate=negate,
            issuer_certificates=issuer_certificates,
        )

        attribute_object_client_certificate.additional_properties = d
        return attribute_object_client_certificate

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
