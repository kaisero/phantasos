from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.custom_type_input import CustomTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.add_remove_urls import AddRemoveUrls
    from ..models.url_input import UrlInput


T = TypeVar("T", bound="CustomPatchApplicationInput")


@_attrs_define
class CustomPatchApplicationInput:
    """
    Attributes:
        type_ (CustomTypeInput): Discriminator field, must be 'custom'.
        name (str | Unset): Name of the application
        description (str | Unset): Description of the application
        urls (AddRemoveUrls | list[UrlInput] | Unset):
        category (str | Unset):
    """

    type_: CustomTypeInput
    name: str | Unset = UNSET
    description: str | Unset = UNSET
    urls: AddRemoveUrls | list[UrlInput] | Unset = UNSET
    category: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        name = self.name

        description = self.description

        urls: dict[str, Any] | list[dict[str, Any]] | Unset
        if isinstance(self.urls, Unset):
            urls = UNSET
        elif isinstance(self.urls, list):
            urls = []
            for componentsschemas_urls_input_item_data in self.urls:
                componentsschemas_urls_input_item = componentsschemas_urls_input_item_data.to_dict()
                urls.append(componentsschemas_urls_input_item)

        else:
            urls = self.urls.to_dict()

        category = self.category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "type": type_,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if urls is not UNSET:
            field_dict["urls"] = urls
        if category is not UNSET:
            field_dict["category"] = category

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.add_remove_urls import AddRemoveUrls
        from ..models.url_input import UrlInput

        d = dict(src_dict)
        type_ = CustomTypeInput(d.pop("type"))

        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        def _parse_urls(data: object) -> AddRemoveUrls | list[UrlInput] | Unset:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_patch_urls_type_0 = []
                _componentsschemas_patch_urls_type_0 = data
                for componentsschemas_urls_input_item_data in _componentsschemas_patch_urls_type_0:
                    componentsschemas_urls_input_item = UrlInput.from_dict(componentsschemas_urls_input_item_data)

                    componentsschemas_patch_urls_type_0.append(componentsschemas_urls_input_item)

                return componentsschemas_patch_urls_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_patch_urls_type_1 = AddRemoveUrls.from_dict(data)

            return componentsschemas_patch_urls_type_1

        urls = _parse_urls(d.pop("urls", UNSET))

        category = d.pop("category", UNSET)

        custom_patch_application_input = cls(
            type_=type_,
            name=name,
            description=description,
            urls=urls,
            category=category,
        )

        custom_patch_application_input.additional_properties = d
        return custom_patch_application_input

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
