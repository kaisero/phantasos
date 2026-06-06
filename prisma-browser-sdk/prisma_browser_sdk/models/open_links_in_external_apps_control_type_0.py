from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.open_links_in_external_apps_control_type_0_action import OpenLinksInExternalAppsControlType0Action
from ..models.open_links_in_external_apps_control_type_0_allowed_apps_item import (
    OpenLinksInExternalAppsControlType0AllowedAppsItem,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="OpenLinksInExternalAppsControlType0")


@_attrs_define
class OpenLinksInExternalAppsControlType0:
    """Control the ability of other apps to open links from Prisma Browser.

    Attributes:
        action (OpenLinksInExternalAppsControlType0Action): Open Links in External Apps action.
        allowed_apps (list[OpenLinksInExternalAppsControlType0AllowedAppsItem] | Unset): Applications allowed to open
            links from the browser when action is 'allowSpecificApps'.
    """

    action: OpenLinksInExternalAppsControlType0Action
    allowed_apps: list[OpenLinksInExternalAppsControlType0AllowedAppsItem] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        allowed_apps: list[str] | Unset = UNSET
        if not isinstance(self.allowed_apps, Unset):
            allowed_apps = []
            for allowed_apps_item_data in self.allowed_apps:
                allowed_apps_item = allowed_apps_item_data.value
                allowed_apps.append(allowed_apps_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if allowed_apps is not UNSET:
            field_dict["allowedApps"] = allowed_apps

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = OpenLinksInExternalAppsControlType0Action(d.pop("action"))

        _allowed_apps = d.pop("allowedApps", UNSET)
        allowed_apps: list[OpenLinksInExternalAppsControlType0AllowedAppsItem] | Unset = UNSET
        if _allowed_apps is not UNSET:
            allowed_apps = []
            for allowed_apps_item_data in _allowed_apps:
                allowed_apps_item = OpenLinksInExternalAppsControlType0AllowedAppsItem(allowed_apps_item_data)

                allowed_apps.append(allowed_apps_item)

        open_links_in_external_apps_control_type_0 = cls(
            action=action,
            allowed_apps=allowed_apps,
        )

        return open_links_in_external_apps_control_type_0
