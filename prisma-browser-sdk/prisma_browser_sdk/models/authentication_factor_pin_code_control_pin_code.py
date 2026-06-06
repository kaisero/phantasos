from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.authentication_factor_pin_code_control_pin_code_max_failed_attempts import (
    AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="AuthenticationFactorPinCodeControlPinCode")


@_attrs_define
class AuthenticationFactorPinCodeControlPinCode:
    """PIN code settings.

    Attributes:
        min_length (int | Unset): Required PIN length. Default: 4.
        max_failed_attempts (AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts | Unset): Maximum failed PIN
            attempts before the user is locked out. Use 0 for unlimited. Default:
            AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts.VALUE_5.
    """

    min_length: int | Unset = 4
    max_failed_attempts: AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts | Unset = (
        AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts.VALUE_5
    )

    def to_dict(self) -> dict[str, Any]:
        min_length = self.min_length

        max_failed_attempts: int | Unset = UNSET
        if not isinstance(self.max_failed_attempts, Unset):
            max_failed_attempts = self.max_failed_attempts.value

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if min_length is not UNSET:
            field_dict["minLength"] = min_length
        if max_failed_attempts is not UNSET:
            field_dict["maxFailedAttempts"] = max_failed_attempts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        min_length = d.pop("minLength", UNSET)

        _max_failed_attempts = d.pop("maxFailedAttempts", UNSET)
        max_failed_attempts: AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts | Unset
        if isinstance(_max_failed_attempts, Unset):
            max_failed_attempts = UNSET
        else:
            max_failed_attempts = AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts(_max_failed_attempts)

        authentication_factor_pin_code_control_pin_code = cls(
            min_length=min_length,
            max_failed_attempts=max_failed_attempts,
        )

        return authentication_factor_pin_code_control_pin_code
