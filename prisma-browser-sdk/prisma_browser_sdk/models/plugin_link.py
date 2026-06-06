from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PluginLink")


@_attrs_define
class PluginLink:
    """
    Attributes:
        url_pattern (str | Unset):
        reset_password_url (str | Unset):
        login_page_url (str | Unset):
    """

    url_pattern: str | Unset = UNSET
    reset_password_url: str | Unset = UNSET
    login_page_url: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        url_pattern = self.url_pattern

        reset_password_url = self.reset_password_url

        login_page_url = self.login_page_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if url_pattern is not UNSET:
            field_dict["urlPattern"] = url_pattern
        if reset_password_url is not UNSET:
            field_dict["resetPasswordUrl"] = reset_password_url
        if login_page_url is not UNSET:
            field_dict["loginPageUrl"] = login_page_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        url_pattern = d.pop("urlPattern", UNSET)

        reset_password_url = d.pop("resetPasswordUrl", UNSET)

        login_page_url = d.pop("loginPageUrl", UNSET)

        plugin_link = cls(
            url_pattern=url_pattern,
            reset_password_url=reset_password_url,
            login_page_url=login_page_url,
        )

        plugin_link.additional_properties = d
        return plugin_link

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
