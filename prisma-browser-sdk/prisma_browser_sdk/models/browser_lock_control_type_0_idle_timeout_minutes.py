from enum import IntEnum


class BrowserLockControlType0IdleTimeoutMinutes(IntEnum):
    VALUE_0 = 0
    VALUE_1 = 1
    VALUE_2 = 2
    VALUE_5 = 5
    VALUE_15 = 15
    VALUE_20 = 20
    VALUE_30 = 30
    VALUE_60 = 60
    VALUE_180 = 180
    VALUE_360 = 360
    VALUE_720 = 720

    def __str__(self) -> str:
        return str(self.value)
