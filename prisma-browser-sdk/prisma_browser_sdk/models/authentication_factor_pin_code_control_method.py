from enum import Enum


class AuthenticationFactorPinCodeControlMethod(str, Enum):
    PINCODE = "pinCode"

    def __str__(self) -> str:
        return str(self.value)
