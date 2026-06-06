from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.browser_self_protection_control_type_0_action import BrowserSelfProtectionControlType0Action
from ..models.browser_self_protection_control_type_0_enforcement import BrowserSelfProtectionControlType0Enforcement
from ..types import UNSET, Unset

T = TypeVar("T", bound="BrowserSelfProtectionControlType0")


@_attrs_define
class BrowserSelfProtectionControlType0:
    """Enables a kernel-mode driver that provides advanced runtime security for the browser. This protection is available
    only on Windows and applies only to devices where Prisma Browser is installed with admin permissions and the user is
    running the browser as admin.

        Attributes:
            action (BrowserSelfProtectionControlType0Action): Whether Browser Self-Protection is enabled.
            enforcement (BrowserSelfProtectionControlType0Enforcement | Unset): Enforcement for Inactive Protection. Applies
                when action is 'enable'. Default: BrowserSelfProtectionControlType0Enforcement.NONE.
    """

    action: BrowserSelfProtectionControlType0Action
    enforcement: BrowserSelfProtectionControlType0Enforcement | Unset = (
        BrowserSelfProtectionControlType0Enforcement.NONE
    )

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        enforcement: str | Unset = UNSET
        if not isinstance(self.enforcement, Unset):
            enforcement = self.enforcement.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if enforcement is not UNSET:
            field_dict["enforcement"] = enforcement

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = BrowserSelfProtectionControlType0Action(d.pop("action"))

        _enforcement = d.pop("enforcement", UNSET)
        enforcement: BrowserSelfProtectionControlType0Enforcement | Unset
        if isinstance(_enforcement, Unset):
            enforcement = UNSET
        else:
            enforcement = BrowserSelfProtectionControlType0Enforcement(_enforcement)

        browser_self_protection_control_type_0 = cls(
            action=action,
            enforcement=enforcement,
        )

        return browser_self_protection_control_type_0
