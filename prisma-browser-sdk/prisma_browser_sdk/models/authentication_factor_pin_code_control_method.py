from .._lenient import LenientStrEnum


class AuthenticationFactorPinCodeControlMethod(LenientStrEnum):
    PINCODE = "pinCode"

    def __str__(self) -> str:
        return str(self.value)
