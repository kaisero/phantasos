from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.launching_external_applications_control_type_0_action import (
    LaunchingExternalApplicationsControlType0Action,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.external_application_launch_exception import ExternalApplicationLaunchException


T = TypeVar("T", bound="LaunchingExternalApplicationsControlType0")


@_attrs_define
class LaunchingExternalApplicationsControlType0:
    """Control whether external applications may launch from Prisma Browser.

    Attributes:
        action (LaunchingExternalApplicationsControlType0Action): How Prisma Browser handles external application launch
            requests.
        exceptions (list[ExternalApplicationLaunchException] | Unset): Application-specific launch handling exceptions.
    """

    action: LaunchingExternalApplicationsControlType0Action
    exceptions: list[ExternalApplicationLaunchException] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        exceptions: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.exceptions, Unset):
            exceptions = []
            for exceptions_item_data in self.exceptions:
                exceptions_item = exceptions_item_data.to_dict()
                exceptions.append(exceptions_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if exceptions is not UNSET:
            field_dict["exceptions"] = exceptions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.external_application_launch_exception import ExternalApplicationLaunchException

        d = dict(src_dict)
        action = LaunchingExternalApplicationsControlType0Action(d.pop("action"))

        _exceptions = d.pop("exceptions", UNSET)
        exceptions: list[ExternalApplicationLaunchException] | Unset = UNSET
        if _exceptions is not UNSET:
            exceptions = []
            for exceptions_item_data in _exceptions:
                exceptions_item = ExternalApplicationLaunchException.from_dict(exceptions_item_data)

                exceptions.append(exceptions_item)

        launching_external_applications_control_type_0 = cls(
            action=action,
            exceptions=exceptions,
        )

        return launching_external_applications_control_type_0
