from enum import Enum


class UserProvider(str, Enum):
    LOCAL = "local"
    OIDC = "oidc"
    SAML = "saml"

    def __str__(self) -> str:
        return str(self.value)
