from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.trusted_certificate_authorities_control_type_0_mode import TrustedCertificateAuthoritiesControlType0Mode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.trusted_certificate_entry import TrustedCertificateEntry


T = TypeVar("T", bound="TrustedCertificateAuthoritiesControlType0")


@_attrs_define
class TrustedCertificateAuthoritiesControlType0:
    """Choose the certificate authorities trusted by Prisma Browser.

    Attributes:
        mode (TrustedCertificateAuthoritiesControlType0Mode): Which certificate store the browser uses to validate
            TLS/SSL certificates. Default: TrustedCertificateAuthoritiesControlType0Mode.DEVICETRUSTSTORE.
        additional_certificates (list[TrustedCertificateEntry] | Unset): Extra trusted CA certificates the browser
            honors in addition to the chosen store.
    """

    mode: TrustedCertificateAuthoritiesControlType0Mode = TrustedCertificateAuthoritiesControlType0Mode.DEVICETRUSTSTORE
    additional_certificates: list[TrustedCertificateEntry] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        mode = self.mode.value

        additional_certificates: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.additional_certificates, Unset):
            additional_certificates = []
            for additional_certificates_item_data in self.additional_certificates:
                additional_certificates_item = additional_certificates_item_data.to_dict()
                additional_certificates.append(additional_certificates_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "mode": mode,
            }
        )
        if additional_certificates is not UNSET:
            field_dict["additionalCertificates"] = additional_certificates

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.trusted_certificate_entry import TrustedCertificateEntry

        d = dict(src_dict)
        mode = TrustedCertificateAuthoritiesControlType0Mode(d.pop("mode"))

        _additional_certificates = d.pop("additionalCertificates", UNSET)
        additional_certificates: list[TrustedCertificateEntry] | Unset = UNSET
        if _additional_certificates is not UNSET:
            additional_certificates = []
            for additional_certificates_item_data in _additional_certificates:
                additional_certificates_item = TrustedCertificateEntry.from_dict(additional_certificates_item_data)

                additional_certificates.append(additional_certificates_item)

        trusted_certificate_authorities_control_type_0 = cls(
            mode=mode,
            additional_certificates=additional_certificates,
        )

        return trusted_certificate_authorities_control_type_0
