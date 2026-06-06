from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.allowed_or_blocked_extensions_control_type_0_mode import AllowedOrBlockedExtensionsControlType0Mode
from ..models.allowed_or_blocked_extensions_control_type_0_risk_level import (
    AllowedOrBlockedExtensionsControlType0RiskLevel,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.allowed_or_blocked_extension_entry import AllowedOrBlockedExtensionEntry


T = TypeVar("T", bound="AllowedOrBlockedExtensionsControlType0")


@_attrs_define
class AllowedOrBlockedExtensionsControlType0:
    """Control browser extension availability to users based on extension ID or risk score.

    Attributes:
        mode (AllowedOrBlockedExtensionsControlType0Mode): Operating mode for Allowed or Blocked Extensions. When
            multiple rules match a user, higher-priority allowAll or blockAll rules override lower-priority extension rules,
            and allowByList allows only the listed extensions.
        extensions (list[AllowedOrBlockedExtensionEntry] | Unset): List of Chrome extension entries to allow or block.
        risk_level (AllowedOrBlockedExtensionsControlType0RiskLevel | Unset): Risk level threshold.
    """

    mode: AllowedOrBlockedExtensionsControlType0Mode
    extensions: list[AllowedOrBlockedExtensionEntry] | Unset = UNSET
    risk_level: AllowedOrBlockedExtensionsControlType0RiskLevel | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        mode = self.mode.value

        extensions: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.extensions, Unset):
            extensions = []
            for extensions_item_data in self.extensions:
                extensions_item = extensions_item_data.to_dict()
                extensions.append(extensions_item)

        risk_level: str | Unset = UNSET
        if not isinstance(self.risk_level, Unset):
            risk_level = self.risk_level.value

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "mode": mode,
            }
        )
        if extensions is not UNSET:
            field_dict["extensions"] = extensions
        if risk_level is not UNSET:
            field_dict["riskLevel"] = risk_level

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.allowed_or_blocked_extension_entry import AllowedOrBlockedExtensionEntry

        d = dict(src_dict)
        mode = AllowedOrBlockedExtensionsControlType0Mode(d.pop("mode"))

        _extensions = d.pop("extensions", UNSET)
        extensions: list[AllowedOrBlockedExtensionEntry] | Unset = UNSET
        if _extensions is not UNSET:
            extensions = []
            for extensions_item_data in _extensions:
                extensions_item = AllowedOrBlockedExtensionEntry.from_dict(extensions_item_data)

                extensions.append(extensions_item)

        _risk_level = d.pop("riskLevel", UNSET)
        risk_level: AllowedOrBlockedExtensionsControlType0RiskLevel | Unset
        if isinstance(_risk_level, Unset):
            risk_level = UNSET
        else:
            risk_level = AllowedOrBlockedExtensionsControlType0RiskLevel(_risk_level)

        allowed_or_blocked_extensions_control_type_0 = cls(
            mode=mode,
            extensions=extensions,
            risk_level=risk_level,
        )

        return allowed_or_blocked_extensions_control_type_0
