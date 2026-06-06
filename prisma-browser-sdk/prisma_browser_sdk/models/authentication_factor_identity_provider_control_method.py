from .._lenient import LenientStrEnum


class AuthenticationFactorIdentityProviderControlMethod(LenientStrEnum):
    IDENTITYPROVIDER = "identityProvider"

    def __str__(self) -> str:
        return str(self.value)
