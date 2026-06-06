from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.legacy_password_manager_control_type_0_action import LegacyPasswordManagerControlType0Action
from ..models.legacy_password_manager_control_type_0_mfa_prompt_frequency_minutes import (
    LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="LegacyPasswordManagerControlType0")


@_attrs_define
class LegacyPasswordManagerControlType0:
    """Enable the Prisma Access Browser legacy password manager for managing and securing company passwords and secrets.

    Attributes:
        action (LegacyPasswordManagerControlType0Action): Whether Legacy Password Manager is enabled.
        mfa_required (bool | Unset): Whether MFA is required before accessing stored passwords.
        mfa_prompt_frequency_minutes (LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes | Unset): How many
            minutes before the user must complete MFA again. Use 0 to require MFA every time.
        disable_password_export (bool | Unset): Whether users are prevented from exporting saved logins.
    """

    action: LegacyPasswordManagerControlType0Action
    mfa_required: bool | Unset = UNSET
    mfa_prompt_frequency_minutes: LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes | Unset = UNSET
    disable_password_export: bool | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        mfa_required = self.mfa_required

        mfa_prompt_frequency_minutes: int | Unset = UNSET
        if not isinstance(self.mfa_prompt_frequency_minutes, Unset):
            mfa_prompt_frequency_minutes = self.mfa_prompt_frequency_minutes.value

        disable_password_export = self.disable_password_export

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if mfa_required is not UNSET:
            field_dict["mfaRequired"] = mfa_required
        if mfa_prompt_frequency_minutes is not UNSET:
            field_dict["mfaPromptFrequencyMinutes"] = mfa_prompt_frequency_minutes
        if disable_password_export is not UNSET:
            field_dict["disablePasswordExport"] = disable_password_export

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = LegacyPasswordManagerControlType0Action(d.pop("action"))

        mfa_required = d.pop("mfaRequired", UNSET)

        _mfa_prompt_frequency_minutes = d.pop("mfaPromptFrequencyMinutes", UNSET)
        mfa_prompt_frequency_minutes: LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes | Unset
        if isinstance(_mfa_prompt_frequency_minutes, Unset):
            mfa_prompt_frequency_minutes = UNSET
        else:
            mfa_prompt_frequency_minutes = LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes(
                _mfa_prompt_frequency_minutes
            )

        disable_password_export = d.pop("disablePasswordExport", UNSET)

        legacy_password_manager_control_type_0 = cls(
            action=action,
            mfa_required=mfa_required,
            mfa_prompt_frequency_minutes=mfa_prompt_frequency_minutes,
            disable_password_export=disable_password_export,
        )

        return legacy_password_manager_control_type_0
