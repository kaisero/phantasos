from enum import IntEnum


class AuthenticationFactorPinCodeControlPinCodeMaxFailedAttempts(IntEnum):
    VALUE_0 = 0
    VALUE_1 = 1
    VALUE_2 = 2
    VALUE_5 = 5
    VALUE_15 = 15
    VALUE_20 = 20
    VALUE_30 = 30

    def __str__(self) -> str:
        return str(self.value)
