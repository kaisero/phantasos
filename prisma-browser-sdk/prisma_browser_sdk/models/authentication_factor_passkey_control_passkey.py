from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="AuthenticationFactorPasskeyControlPasskey")


@_attrs_define
class AuthenticationFactorPasskeyControlPasskey:
    """Passkey authenticator settings.

    Attributes:
        internal_authenticator (bool): Allow passkeys from device-bound authenticators such as Windows Hello or macOS
            Keychain.
        external_authenticator (bool): Allow passkeys from external authenticators such as Yubikey, smartcard, or mobile
            phone.
    """

    internal_authenticator: bool
    external_authenticator: bool

    def to_dict(self) -> dict[str, Any]:
        internal_authenticator = self.internal_authenticator

        external_authenticator = self.external_authenticator

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "internalAuthenticator": internal_authenticator,
                "externalAuthenticator": external_authenticator,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        internal_authenticator = d.pop("internalAuthenticator")

        external_authenticator = d.pop("externalAuthenticator")

        authentication_factor_passkey_control_passkey = cls(
            internal_authenticator=internal_authenticator,
            external_authenticator=external_authenticator,
        )

        return authentication_factor_passkey_control_passkey
