from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.authentication_factor_identity_provider_control_identity_provider_profile_source import (
    AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="AuthenticationFactorIdentityProviderControlIdentityProvider")


@_attrs_define
class AuthenticationFactorIdentityProviderControlIdentityProvider:
    """Identity provider settings.

    Attributes:
        profile_source (AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource | Unset): Whether to
            use the configured authentication profile or specify a custom one. Default:
            AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource.USECONFIGUREDAUTHPROFILE.
        auth_profile_id (str | Unset): Authentication profile ID to use when profileSource is 'custom'.
        incognito (bool | Unset): Whether to perform IdP authentication in an isolated browser session. Default: True.
        force_reauthentication (bool | Unset): Whether to force re-authentication with the IdP rather than using an
            existing session. Default: True.
    """

    profile_source: AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource | Unset = (
        AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource.USECONFIGUREDAUTHPROFILE
    )
    auth_profile_id: str | Unset = UNSET
    incognito: bool | Unset = True
    force_reauthentication: bool | Unset = True

    def to_dict(self) -> dict[str, Any]:
        profile_source: str | Unset = UNSET
        if not isinstance(self.profile_source, Unset):
            profile_source = self.profile_source.value

        auth_profile_id = self.auth_profile_id

        incognito = self.incognito

        force_reauthentication = self.force_reauthentication

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if profile_source is not UNSET:
            field_dict["profileSource"] = profile_source
        if auth_profile_id is not UNSET:
            field_dict["authProfileId"] = auth_profile_id
        if incognito is not UNSET:
            field_dict["incognito"] = incognito
        if force_reauthentication is not UNSET:
            field_dict["forceReauthentication"] = force_reauthentication

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _profile_source = d.pop("profileSource", UNSET)
        profile_source: AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource | Unset
        if isinstance(_profile_source, Unset):
            profile_source = UNSET
        else:
            profile_source = AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource(_profile_source)

        auth_profile_id = d.pop("authProfileId", UNSET)

        incognito = d.pop("incognito", UNSET)

        force_reauthentication = d.pop("forceReauthentication", UNSET)

        authentication_factor_identity_provider_control_identity_provider = cls(
            profile_source=profile_source,
            auth_profile_id=auth_profile_id,
            incognito=incognito,
            force_reauthentication=force_reauthentication,
        )

        return authentication_factor_identity_provider_control_identity_provider
