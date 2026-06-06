from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UrlInput")


@_attrs_define
class UrlInput:
    """
    Attributes:
        url (str): URL pattern expression
        strict_mode (bool | Unset): If `true`, the URL is saved exactly as entered.
            If `false` (default), the system automatically normalizes the URL based on the App Type:

            **Custom Apps:**
            * **Protocol:** Defaults to `*://` if omitted.
            * **Subdomain:** Defaults to `www` logic (hidden).
            * **Path:** Appends `/*` if no path is specified.

            **Private Apps:**
            * **Protocol:** Defaults to `https://`. Wildcards (`*`) are **NOT** allowed.
            * **Subdomain:** No automatic `www` handling; `www` is treated as a unique prefix.
            * **Domain:** Supports IPv4 and Port numbers (e.g., `:8080`).
            * **Path:** Automatically adds a trailing `*` to all paths.
             Default: False.
    """

    url: str
    strict_mode: bool | Unset = False
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        url = self.url

        strict_mode = self.strict_mode

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "url": url,
            }
        )
        if strict_mode is not UNSET:
            field_dict["strict_mode"] = strict_mode

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url = d.pop("url")

        strict_mode = d.pop("strict_mode", UNSET)

        url_input = cls(
            url=url,
            strict_mode=strict_mode,
        )

        url_input.additional_properties = d
        return url_input

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
