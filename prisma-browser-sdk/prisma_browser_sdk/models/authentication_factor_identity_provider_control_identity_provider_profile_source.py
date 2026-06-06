from .._lenient import LenientStrEnum


class AuthenticationFactorIdentityProviderControlIdentityProviderProfileSource(LenientStrEnum):
    CUSTOM = "custom"
    USECONFIGUREDAUTHPROFILE = "useConfiguredAuthProfile"

    def __str__(self) -> str:
        return str(self.value)
