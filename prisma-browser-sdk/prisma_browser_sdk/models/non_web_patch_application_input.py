from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.nonweb_type_input import NonwebTypeInput
from ..types import UNSET, Unset

T = TypeVar("T", bound="NonWebPatchApplicationInput")


@_attrs_define
class NonWebPatchApplicationInput:
    """
    Attributes:
        type_ (NonwebTypeInput): Discriminator field, must be 'non-web'.
        name (str | Unset): Name of the application
        description (str | Unset): Description of the application
        address (str | Unset):
        protocol (str | Unset):
        port (str | Unset):
        route_to_prisma (bool | Unset):
    """

    type_: NonwebTypeInput
    name: str | Unset = UNSET
    description: str | Unset = UNSET
    address: str | Unset = UNSET
    protocol: str | Unset = UNSET
    port: str | Unset = UNSET
    route_to_prisma: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        name = self.name

        description = self.description

        address = self.address

        protocol = self.protocol

        port = self.port

        route_to_prisma = self.route_to_prisma

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
        if address is not UNSET:
            field_dict["address"] = address
        if protocol is not UNSET:
            field_dict["protocol"] = protocol
        if port is not UNSET:
            field_dict["port"] = port
        if route_to_prisma is not UNSET:
            field_dict["routeToPrisma"] = route_to_prisma

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = NonwebTypeInput(d.pop("type"))

        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        address = d.pop("address", UNSET)

        protocol = d.pop("protocol", UNSET)

        port = d.pop("port", UNSET)

        route_to_prisma = d.pop("routeToPrisma", UNSET)

        non_web_patch_application_input = cls(
            type_=type_,
            name=name,
            description=description,
            address=address,
            protocol=protocol,
            port=port,
            route_to_prisma=route_to_prisma,
        )

        non_web_patch_application_input.additional_properties = d
        return non_web_patch_application_input

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
