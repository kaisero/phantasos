from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.allowed_printers_control_type_0_action import AllowedPrintersControlType0Action
from ..types import UNSET, Unset

T = TypeVar("T", bound="AllowedPrintersControlType0")


@_attrs_define
class AllowedPrintersControlType0:
    """Control which printers can be used when printing from Prisma Browser.

    Attributes:
        action (AllowedPrintersControlType0Action): Whether any printer is allowed or only specific printers from a
            list.
        allowed_printers (list[str] | Unset): Printer identifiers allowed when action is 'allowSpecific'.
        allow_save_as_pdf (bool | Unset): Whether to allow 'Save as PDF' when action is 'allowSpecific'. Dashboard shows
            this behind showSaveAsPdfCheckbox. Default: True.
    """

    action: AllowedPrintersControlType0Action
    allowed_printers: list[str] | Unset = UNSET
    allow_save_as_pdf: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        allowed_printers: list[str] | Unset = UNSET
        if not isinstance(self.allowed_printers, Unset):
            allowed_printers = self.allowed_printers

        allow_save_as_pdf = self.allow_save_as_pdf

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if allowed_printers is not UNSET:
            field_dict["allowedPrinters"] = allowed_printers
        if allow_save_as_pdf is not UNSET:
            field_dict["allowSaveAsPdf"] = allow_save_as_pdf

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = AllowedPrintersControlType0Action(d.pop("action"))

        allowed_printers = cast(list[str], d.pop("allowedPrinters", UNSET))

        allow_save_as_pdf = d.pop("allowSaveAsPdf", UNSET)

        allowed_printers_control_type_0 = cls(
            action=action,
            allowed_printers=allowed_printers,
            allow_save_as_pdf=allow_save_as_pdf,
        )

        return allowed_printers_control_type_0
