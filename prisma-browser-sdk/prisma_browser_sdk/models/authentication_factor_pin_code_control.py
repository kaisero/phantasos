from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.authentication_factor_pin_code_control_method import AuthenticationFactorPinCodeControlMethod

if TYPE_CHECKING:
    from ..models.authentication_factor_pin_code_control_pin_code import AuthenticationFactorPinCodeControlPinCode


T = TypeVar("T", bound="AuthenticationFactorPinCodeControl")


@_attrs_define
class AuthenticationFactorPinCodeControl:
    """PIN code authentication factor settings.

    Attributes:
        method (AuthenticationFactorPinCodeControlMethod): Method used for browser unlock and step-up MFA.
        pin_code (AuthenticationFactorPinCodeControlPinCode): PIN code settings.
    """

    method: AuthenticationFactorPinCodeControlMethod
    pin_code: AuthenticationFactorPinCodeControlPinCode

    def to_dict(self) -> dict[str, Any]:
        method = self.method.value

        pin_code = self.pin_code.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "method": method,
                "pinCode": pin_code,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.authentication_factor_pin_code_control_pin_code import AuthenticationFactorPinCodeControlPinCode

        d = dict(src_dict)
        method = AuthenticationFactorPinCodeControlMethod(d.pop("method"))

        pin_code = AuthenticationFactorPinCodeControlPinCode.from_dict(d.pop("pinCode"))

        authentication_factor_pin_code_control = cls(
            method=method,
            pin_code=pin_code,
        )

        return authentication_factor_pin_code_control
