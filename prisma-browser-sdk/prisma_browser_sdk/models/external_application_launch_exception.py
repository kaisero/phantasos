from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.external_application_launch_exception_action import ExternalApplicationLaunchExceptionAction

T = TypeVar("T", bound="ExternalApplicationLaunchException")


@_attrs_define
class ExternalApplicationLaunchException:
    """
    Attributes:
        name (str):
        action (ExternalApplicationLaunchExceptionAction):
        protocol_schemes (list[str]):
    """

    name: str
    action: ExternalApplicationLaunchExceptionAction
    protocol_schemes: list[str]

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        action = self.action.value

        protocol_schemes = self.protocol_schemes

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "action": action,
                "protocolSchemes": protocol_schemes,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        action = ExternalApplicationLaunchExceptionAction(d.pop("action"))

        protocol_schemes = cast(list[str], d.pop("protocolSchemes"))

        external_application_launch_exception = cls(
            name=name,
            action=action,
            protocol_schemes=protocol_schemes,
        )

        return external_application_launch_exception
