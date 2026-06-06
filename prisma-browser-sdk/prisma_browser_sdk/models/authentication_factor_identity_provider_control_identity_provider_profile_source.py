from enum import Enum


class AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource(str, Enum):
    CUSTOM = "custom"
    USECONFIGUREDAUTHPROFILE = "useConfiguredAuthProfile"

    def __str__(self) -> str:
        return str(self.value)
