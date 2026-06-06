from enum import Enum


class AuthenticationFactorPasskeyControlMethod(str, Enum):
    PASSKEY = "passkey"

    def __str__(self) -> str:
        return str(self.value)
