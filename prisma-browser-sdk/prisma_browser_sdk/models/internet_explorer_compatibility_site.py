from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.internet_explorer_compatibility_site_document_mode import InternetExplorerCompatibilitySiteDocumentMode
from ..types import UNSET, Unset

T = TypeVar("T", bound="InternetExplorerCompatibilitySite")


@_attrs_define
class InternetExplorerCompatibilitySite:
    """
    Attributes:
        url (str):
        document_mode (InternetExplorerCompatibilitySiteDocumentMode | Unset):
    """

    url: str
    document_mode: InternetExplorerCompatibilitySiteDocumentMode | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        url = self.url

        document_mode: str | Unset = UNSET
        if not isinstance(self.document_mode, Unset):
            document_mode = self.document_mode.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "url": url,
            }
        )
        if document_mode is not UNSET:
            field_dict["documentMode"] = document_mode

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url = d.pop("url")

        _document_mode = d.pop("documentMode", UNSET)
        document_mode: InternetExplorerCompatibilitySiteDocumentMode | Unset
        if isinstance(_document_mode, Unset):
            document_mode = UNSET
        else:
            document_mode = InternetExplorerCompatibilitySiteDocumentMode(_document_mode)

        internet_explorer_compatibility_site = cls(
            url=url,
            document_mode=document_mode,
        )

        return internet_explorer_compatibility_site
