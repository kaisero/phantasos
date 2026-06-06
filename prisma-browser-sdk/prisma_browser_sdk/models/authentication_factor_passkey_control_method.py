from .._lenient import LenientStrEnum


class AuthenticationFactorPasskeyControlMethod(LenientStrEnum):
    PASSKEY = "passkey"

    def __str__(self) -> str:
        return str(self.value)
