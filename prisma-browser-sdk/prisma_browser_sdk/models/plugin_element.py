from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.plugin_element_element_type import PluginElementElementType
from ..types import UNSET, Unset

T = TypeVar("T", bound="PluginElement")


@_attrs_define
class PluginElement:
    """
    Attributes:
        element_type (PluginElementElementType):
        selectors (list[str]):
        url_pattern (str | Unset):
    """

    element_type: PluginElementElementType
    selectors: list[str]
    url_pattern: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        element_type = self.element_type.value

        selectors = self.selectors

        url_pattern = self.url_pattern

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "elementType": element_type,
                "selectors": selectors,
            }
        )
        if url_pattern is not UNSET:
            field_dict["urlPattern"] = url_pattern

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        element_type = PluginElementElementType(d.pop("elementType"))

        selectors = cast(list[str], d.pop("selectors"))

        url_pattern = d.pop("urlPattern", UNSET)

        plugin_element = cls(
            element_type=element_type,
            selectors=selectors,
            url_pattern=url_pattern,
        )

        plugin_element.additional_properties = d
        return plugin_element

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
