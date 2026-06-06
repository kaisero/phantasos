from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.authentication_factor_passkey_control_method import AuthenticationFactorPasskeyControlMethod

if TYPE_CHECKING:
    from ..models.authentication_factor_passkey_control_passkey import AuthenticationFactorPasskeyControlPasskey


T = TypeVar("T", bound="AuthenticationFactorPasskeyControl")


@_attrs_define
class AuthenticationFactorPasskeyControl:
    """Passkey authentication factor settings.

    Attributes:
        method (AuthenticationFactorPasskeyControlMethod): Method used for browser unlock and step-up MFA.
        passkey (AuthenticationFactorPasskeyControlPasskey): Passkey authenticator settings.
    """

    method: AuthenticationFactorPasskeyControlMethod
    passkey: AuthenticationFactorPasskeyControlPasskey

    def to_dict(self) -> dict[str, Any]:
        method = self.method.value

        passkey = self.passkey.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "method": method,
                "passkey": passkey,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.authentication_factor_passkey_control_passkey import AuthenticationFactorPasskeyControlPasskey

        d = dict(src_dict)
        method = AuthenticationFactorPasskeyControlMethod(d.pop("method"))

        passkey = AuthenticationFactorPasskeyControlPasskey.from_dict(d.pop("passkey"))

        authentication_factor_passkey_control = cls(
            method=method,
            passkey=passkey,
        )

        return authentication_factor_passkey_control
