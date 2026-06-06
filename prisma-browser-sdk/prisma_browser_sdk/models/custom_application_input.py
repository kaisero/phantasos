from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.custom_type_input import CustomTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.url_input import UrlInput


T = TypeVar("T", bound="CustomApplicationInput")


@_attrs_define
class CustomApplicationInput:
    """
    Attributes:
        name (str): Name of the application
        type_ (CustomTypeInput): Discriminator field, must be 'custom'.
        urls (list[UrlInput]): URL patterns for the application. Maximum 100 URLs allowed.
        description (str | Unset): Description of the application
        category (str | Unset):
    """

    name: str
    type_: CustomTypeInput
    urls: list[UrlInput]
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_.value

        urls = []
        for componentsschemas_urls_input_item_data in self.urls:
            componentsschemas_urls_input_item = componentsschemas_urls_input_item_data.to_dict()
            urls.append(componentsschemas_urls_input_item)

        description = self.description

        category = self.category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "type": type_,
                "urls": urls,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if category is not UNSET:
            field_dict["category"] = category

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.url_input import UrlInput

        d = dict(src_dict)
        name = d.pop("name")

        type_ = CustomTypeInput(d.pop("type"))

        urls = []
        _urls = d.pop("urls")
        for componentsschemas_urls_input_item_data in _urls:
            componentsschemas_urls_input_item = UrlInput.from_dict(componentsschemas_urls_input_item_data)

            urls.append(componentsschemas_urls_input_item)

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        custom_application_input = cls(
            name=name,
            type_=type_,
            urls=urls,
            description=description,
            category=category,
        )

        custom_application_input.additional_properties = d
        return custom_application_input

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
