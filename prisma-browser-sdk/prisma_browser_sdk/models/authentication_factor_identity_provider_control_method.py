from enum import Enum


class AuthenticationFactorIdentityProviderControlMethod(str, Enum):
    IDENTITYPROVIDER = "identityProvider"

    def __str__(self) -> str:
        return str(self.value)
