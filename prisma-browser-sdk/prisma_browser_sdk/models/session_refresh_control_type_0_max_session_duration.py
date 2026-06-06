from enum import Enum


class SessionRefreshControlType0MaxSessionDuration(str, Enum):
    VALUE_0 = "1hour"
    VALUE_1 = "4hours"
    VALUE_2 = "9hours"
    VALUE_3 = "12hours"
    VALUE_4 = "24hours"
    VALUE_5 = "3days"
    VALUE_6 = "7days"
    VALUE_7 = "14days"
    VALUE_8 = "30days"

    def __str__(self) -> str:
        return str(self.value)
