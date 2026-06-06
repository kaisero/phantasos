from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.non_web_application_type import NonWebApplicationType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.metadata import Metadata


T = TypeVar("T", bound="NonWebApplication")


@_attrs_define
class NonWebApplication:
    """Non-Web Application

    Attributes:
        id (str): Unique identifier
        name (str): Name of the application
        type_ (NonWebApplicationType): Discriminator field, must be 'non-web'.
        metadata (Metadata):
        urls (list[str]): URL patterns for the application
        description (str | Unset): Description of the application
        category (str | Unset):
        protocol (str | Unset):
        port (str | Unset):
        route_to_prisma (bool | Unset):
    """

    id: str
    name: str
    type_: NonWebApplicationType
    metadata: Metadata
    urls: list[str]
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    protocol: str | Unset = UNSET
    port: str | Unset = UNSET
    route_to_prisma: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        type_ = self.type_.value

        metadata = self.metadata.to_dict()

        urls = self.urls

        description = self.description

        category = self.category

        protocol = self.protocol

        port = self.port

        route_to_prisma = self.route_to_prisma

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
        if protocol is not UNSET:
            field_dict["protocol"] = protocol
        if port is not UNSET:
            field_dict["port"] = port
        if route_to_prisma is not UNSET:
            field_dict["routeToPrisma"] = route_to_prisma

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.metadata import Metadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        type_ = NonWebApplicationType(d.pop("type"))

        metadata = Metadata.from_dict(d.pop("metadata"))

        urls = cast(list[str], d.pop("urls"))

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        protocol = d.pop("protocol", UNSET)

        port = d.pop("port", UNSET)

        route_to_prisma = d.pop("routeToPrisma", UNSET)

        non_web_application = cls(
            id=id,
            name=name,
            type_=type_,
            metadata=metadata,
            urls=urls,
            description=description,
            category=category,
            protocol=protocol,
            port=port,
            route_to_prisma=route_to_prisma,
        )

        non_web_application.additional_properties = d
        return non_web_application

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
