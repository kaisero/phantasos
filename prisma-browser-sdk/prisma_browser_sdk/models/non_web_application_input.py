from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.nonweb_type_input import NonwebTypeInput
from ..types import UNSET, Unset

T = TypeVar("T", bound="NonWebApplicationInput")


@_attrs_define
class NonWebApplicationInput:
    """
    Attributes:
        name (str): Name of the application
        type_ (NonwebTypeInput): Discriminator field, must be 'non-web'.
        address (str):
        protocol (str):
        port (str):
        description (str | Unset): Description of the application
        route_to_prisma (bool | Unset):
    """

    name: str
    type_: NonwebTypeInput
    address: str
    protocol: str
    port: str
    description: str | Unset = UNSET
    route_to_prisma: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        type_ = self.type_.value

        address = self.address

        protocol = self.protocol

        port = self.port

        description = self.description

        route_to_prisma = self.route_to_prisma

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "name": name,
                "type": type_,
                "address": address,
                "protocol": protocol,
                "port": port,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if route_to_prisma is not UNSET:
            field_dict["routeToPrisma"] = route_to_prisma

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        type_ = NonwebTypeInput(d.pop("type"))

        address = d.pop("address")

        protocol = d.pop("protocol")

        port = d.pop("port")

        description = d.pop("description", UNSET)

        route_to_prisma = d.pop("routeToPrisma", UNSET)

        non_web_application_input = cls(
            name=name,
            type_=type_,
            address=address,
            protocol=protocol,
            port=port,
            description=description,
            route_to_prisma=route_to_prisma,
        )

        non_web_application_input.additional_properties = d
        return non_web_application_input

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
