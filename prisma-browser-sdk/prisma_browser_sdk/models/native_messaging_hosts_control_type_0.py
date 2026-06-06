from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.native_messaging_hosts_control_type_0_action import NativeMessagingHostsControlType0Action

T = TypeVar("T", bound="NativeMessagingHostsControlType0")


@_attrs_define
class NativeMessagingHostsControlType0:
    """Control which native messaging hosts can communicate with Prisma Browser and its extensions.

    Attributes:
        action (NativeMessagingHostsControlType0Action): Native Messaging Hosts action.
    """

    action: NativeMessagingHostsControlType0Action

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = NativeMessagingHostsControlType0Action(d.pop("action"))

        native_messaging_hosts_control_type_0 = cls(
            action=action,
        )

        return native_messaging_hosts_control_type_0
