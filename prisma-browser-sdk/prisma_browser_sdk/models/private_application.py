from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.private_application_type import PrivateApplicationType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.metadata import Metadata


T = TypeVar("T", bound="PrivateApplication")


@_attrs_define
class PrivateApplication:
    """Private Application

    Attributes:
        id (str): Unique identifier
        name (str): Name of the application
        type_ (PrivateApplicationType): Discriminator field, must be 'private'.
        metadata (Metadata):
        urls (list[str]): URL patterns for the application
        description (str | Unset): Description of the application
        category (str | Unset):
        primary_url (str | Unset):
        route_to_prisma (bool | Unset):
        domain_suffix (None | str | Unset): DNS suffix appended to single-label hostnames (for example,
            corp.example.com). Required when any URL or primary URL uses a short hostname.
        cidrs (list[str] | Unset): CIDR ranges for the private application. IPv4 only, /8 to /32.
    """

    id: str
    name: str
    type_: PrivateApplicationType
    metadata: Metadata
    urls: list[str]
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    primary_url: str | Unset = UNSET
    route_to_prisma: bool | Unset = UNSET
    domain_suffix: None | str | Unset = UNSET
    cidrs: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        type_ = self.type_.value

        metadata = self.metadata.to_dict()

        urls = self.urls

        description = self.description

        category = self.category

        primary_url = self.primary_url

        route_to_prisma = self.route_to_prisma

        domain_suffix: None | str | Unset
        if isinstance(self.domain_suffix, Unset):
            domain_suffix = UNSET
        else:
            domain_suffix = self.domain_suffix

        cidrs: list[str] | Unset = UNSET
        if not isinstance(self.cidrs, Unset):
            cidrs = self.cidrs

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "type": type_,
                "metadata": metadata,
                "urls": urls,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if category is not UNSET:
            field_dict["category"] = category
        if primary_url is not UNSET:
            field_dict["primaryUrl"] = primary_url
        if route_to_prisma is not UNSET:
            field_dict["routeToPrisma"] = route_to_prisma
        if domain_suffix is not UNSET:
            field_dict["domainSuffix"] = domain_suffix
        if cidrs is not UNSET:
            field_dict["cidrs"] = cidrs

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.metadata import Metadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        type_ = PrivateApplicationType(d.pop("type"))

        metadata = Metadata.from_dict(d.pop("metadata"))

        urls = cast(list[str], d.pop("urls"))

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        primary_url = d.pop("primaryUrl", UNSET)

        route_to_prisma = d.pop("routeToPrisma", UNSET)

        def _parse_domain_suffix(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        domain_suffix = _parse_domain_suffix(d.pop("domainSuffix", UNSET))

        cidrs = cast(list[str], d.pop("cidrs", UNSET))

        private_application = cls(
            id=id,
            name=name,
            type_=type_,
            metadata=metadata,
            urls=urls,
            description=description,
            category=category,
            primary_url=primary_url,
            route_to_prisma=route_to_prisma,
            domain_suffix=domain_suffix,
            cidrs=cidrs,
        )

        private_application.additional_properties = d
        return private_application

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
