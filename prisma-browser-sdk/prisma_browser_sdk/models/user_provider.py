from .._lenient import LenientStrEnum


class UserProvider(LenientStrEnum):
    LOCAL = "local"
    OIDC = "oidc"
    SAML = "saml"

    def __str__(self) -> str:
        return str(self.value)
