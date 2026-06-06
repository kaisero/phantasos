from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.private_type_input import PrivateTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.add_remove_cidrs import AddRemoveCidrs
    from ..models.add_remove_urls import AddRemoveUrls
    from ..models.url_input import UrlInput


T = TypeVar("T", bound="PrivatePatchApplicationInput")


@_attrs_define
class PrivatePatchApplicationInput:
    """
    Attributes:
        type_ (PrivateTypeInput): Discriminator field, must be 'private'.
        name (str | Unset): Name of the application
        description (str | Unset): Description of the application
        urls (AddRemoveUrls | list[UrlInput] | Unset):
        primary_url (str | Unset):
        route_to_prisma (bool | Unset):
        cidrs (AddRemoveCidrs | list[str] | Unset):
        category (str | Unset):
        domain_suffix (None | str | Unset): DNS suffix appended to single-label hostnames (for example,
            corp.example.com). To update: set a string; use JSON null to clear; omit the property to leave unchanged.
    """

    type_: PrivateTypeInput
    name: str | Unset = UNSET
    description: str | Unset = UNSET
    urls: AddRemoveUrls | list[UrlInput] | Unset = UNSET
    primary_url: str | Unset = UNSET
    route_to_prisma: bool | Unset = UNSET
    cidrs: AddRemoveCidrs | list[str] | Unset = UNSET
    category: str | Unset = UNSET
    domain_suffix: None | str | Unset = UNSET
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

        primary_url = self.primary_url

        route_to_prisma = self.route_to_prisma

        cidrs: dict[str, Any] | list[str] | Unset
        if isinstance(self.cidrs, Unset):
            cidrs = UNSET
        elif isinstance(self.cidrs, list):
            cidrs = self.cidrs

        else:
            cidrs = self.cidrs.to_dict()

        category = self.category

        domain_suffix: None | str | Unset
        if isinstance(self.domain_suffix, Unset):
            domain_suffix = UNSET
        else:
            domain_suffix = self.domain_suffix

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
        if primary_url is not UNSET:
            field_dict["primaryUrl"] = primary_url
        if route_to_prisma is not UNSET:
            field_dict["routeToPrisma"] = route_to_prisma
        if cidrs is not UNSET:
            field_dict["cidrs"] = cidrs
        if category is not UNSET:
            field_dict["category"] = category
        if domain_suffix is not UNSET:
            field_dict["domainSuffix"] = domain_suffix

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.add_remove_cidrs import AddRemoveCidrs
        from ..models.add_remove_urls import AddRemoveUrls
        from ..models.url_input import UrlInput

        d = dict(src_dict)
        type_ = PrivateTypeInput(d.pop("type"))

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

        primary_url = d.pop("primaryUrl", UNSET)

        route_to_prisma = d.pop("routeToPrisma", UNSET)

        def _parse_cidrs(data: object) -> AddRemoveCidrs | list[str] | Unset:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                componentsschemas_patch_cidrs_type_0 = cast(list[str], data)

                return componentsschemas_patch_cidrs_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            componentsschemas_patch_cidrs_type_1 = AddRemoveCidrs.from_dict(data)

            return componentsschemas_patch_cidrs_type_1

        cidrs = _parse_cidrs(d.pop("cidrs", UNSET))

        category = d.pop("category", UNSET)

        def _parse_domain_suffix(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        domain_suffix = _parse_domain_suffix(d.pop("domainSuffix", UNSET))

        private_patch_application_input = cls(
            type_=type_,
            name=name,
            description=description,
            urls=urls,
            primary_url=primary_url,
            route_to_prisma=route_to_prisma,
            cidrs=cidrs,
            category=category,
            domain_suffix=domain_suffix,
        )

        private_patch_application_input.additional_properties = d
        return private_patch_application_input

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
