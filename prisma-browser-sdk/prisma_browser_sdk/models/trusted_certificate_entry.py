from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="TrustedCertificateEntry")


@_attrs_define
class TrustedCertificateEntry:
    """
    Attributes:
        name (str): Display name for the certificate.
        content (str): The certificate itself, as a single base64 string.
    """

    name: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        content = self.content

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "content": content,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        content = d.pop("content")

        trusted_certificate_entry = cls(
            name=name,
            content=content,
        )

        return trusted_certificate_entry
