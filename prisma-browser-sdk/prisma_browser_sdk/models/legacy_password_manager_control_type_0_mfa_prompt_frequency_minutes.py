from enum import IntEnum


class LegacyPasswordManagerControlType0MfaPromptFrequencyMinutes(IntEnum):
    VALUE_0 = 0
    VALUE_1 = 1
    VALUE_2 = 2
    VALUE_5 = 5
    VALUE_10 = 10
    VALUE_20 = 20
    VALUE_30 = 30

    def __str__(self) -> str:
        return str(self.value)
