from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.authentication_factor_identity_provider_control_method import (
    AuthenticationFactorIdentityProviderControlMethod,
)

if TYPE_CHECKING:
    from ..models.authentication_factor_identity_provider_control_identity_provider import (
        AuthenticationFactorIdentityProviderControlIdentityProvider,
    )


T = TypeVar("T", bound="AuthenticationFactorIdentityProviderControl")


@_attrs_define
class AuthenticationFactorIdentityProviderControl:
    """Identity provider authentication factor settings.

    Attributes:
        method (AuthenticationFactorIdentityProviderControlMethod): Method used for browser unlock and step-up MFA.
        identity_provider (AuthenticationFactorIdentityProviderControlIdentityProvider): Identity provider settings.
    """

    method: AuthenticationFactorIdentityProviderControlMethod
    identity_provider: AuthenticationFactorIdentityProviderControlIdentityProvider

    def to_dict(self) -> dict[str, Any]:
        method = self.method.value

        identity_provider = self.identity_provider.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "method": method,
                "identityProvider": identity_provider,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.authentication_factor_identity_provider_control_identity_provider import (
            AuthenticationFactorIdentityProviderControlIdentityProvider,
        )

        d = dict(src_dict)
        method = AuthenticationFactorIdentityProviderControlMethod(d.pop("method"))

        identity_provider = AuthenticationFactorIdentityProviderControlIdentityProvider.from_dict(
            d.pop("identityProvider")
        )

        authentication_factor_identity_provider_control = cls(
            method=method,
            identity_provider=identity_provider,
        )

        return authentication_factor_identity_provider_control
