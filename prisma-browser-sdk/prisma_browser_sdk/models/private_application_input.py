from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.private_type_input import PrivateTypeInput
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.url_input import UrlInput


T = TypeVar("T", bound="PrivateApplicationInput")


@_attrs_define
class PrivateApplicationInput:
    """
    Attributes:
        name (str): Name of the application
        type_ (PrivateTypeInput): Discriminator field, must be 'private'.
        urls (list[UrlInput]): URL patterns for the application. Maximum 100 URLs allowed.
        primary_url (str):
        route_to_prisma (bool):
        description (str | Unset): Description of the application
        cidrs (list[str] | Unset): CIDR ranges for the private application. IPv4 only, /8 to /32.
        category (str | Unset):
        domain_suffix (None | str | Unset): DNS suffix appended to single-label hostnames (for example,
            corp.example.com). Required when any URL or primary URL uses a short hostname.
    """

    name: str
    type_: PrivateTypeInput
    urls: list[UrlInput]
    primary_url: str
    route_to_prisma: bool
    description: str | Unset = UNSET
    cidrs: list[str] | Unset = UNSET
    category: str | Unset = UNSET
    domain_suffix: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_.value

        urls = []
        for componentsschemas_urls_input_item_data in self.urls:
            componentsschemas_urls_input_item = componentsschemas_urls_input_item_data.to_dict()
            urls.append(componentsschemas_urls_input_item)

        primary_url = self.primary_url

        route_to_prisma = self.route_to_prisma

        description = self.description

        cidrs: list[str] | Unset = UNSET
        if not isinstance(self.cidrs, Unset):
            cidrs = self.cidrs

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
                "name": name,
                "type": type_,
                "urls": urls,
                "primaryUrl": primary_url,
                "routeToPrisma": route_to_prisma,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if cidrs is not UNSET:
            field_dict["cidrs"] = cidrs
        if category is not UNSET:
            field_dict["category"] = category
        if domain_suffix is not UNSET:
            field_dict["domainSuffix"] = domain_suffix

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.url_input import UrlInput

        d = dict(src_dict)
        name = d.pop("name")

        type_ = PrivateTypeInput(d.pop("type"))

        urls = []
        _urls = d.pop("urls")
        for componentsschemas_urls_input_item_data in _urls:
            componentsschemas_urls_input_item = UrlInput.from_dict(componentsschemas_urls_input_item_data)

            urls.append(componentsschemas_urls_input_item)

        primary_url = d.pop("primaryUrl")

        route_to_prisma = d.pop("routeToPrisma")

        description = d.pop("description", UNSET)

        cidrs = cast(list[str], d.pop("cidrs", UNSET))

        category = d.pop("category", UNSET)

        def _parse_domain_suffix(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        domain_suffix = _parse_domain_suffix(d.pop("domainSuffix", UNSET))

        private_application_input = cls(
            name=name,
            type_=type_,
            urls=urls,
            primary_url=primary_url,
            route_to_prisma=route_to_prisma,
            description=description,
            cidrs=cidrs,
            category=category,
            domain_suffix=domain_suffix,
        )

        private_application_input.additional_properties = d
        return private_application_input

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
