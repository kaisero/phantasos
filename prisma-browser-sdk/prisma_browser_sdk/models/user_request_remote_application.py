from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UserRequestRemoteApplication")


@_attrs_define
class UserRequestRemoteApplication:
    """
    Attributes:
        name (str | Unset): Remote connection
        address (str | Unset): IP Address
        port (int | Unset): Port
        protocol (str | Unset): Protocol
    """

    name: str | Unset = UNSET
    address: str | Unset = UNSET
    port: int | Unset = UNSET
    protocol: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        address = self.address

        port = self.port

        protocol = self.protocol

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if address is not UNSET:
            field_dict["address"] = address
        if port is not UNSET:
            field_dict["port"] = port
        if protocol is not UNSET:
            field_dict["protocol"] = protocol

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name", UNSET)

        address = d.pop("address", UNSET)

        port = d.pop("port", UNSET)

        protocol = d.pop("protocol", UNSET)

        user_request_remote_application = cls(
            name=name,
            address=address,
            port=port,
            protocol=protocol,
        )

        user_request_remote_application.additional_properties = d
        return user_request_remote_application

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
