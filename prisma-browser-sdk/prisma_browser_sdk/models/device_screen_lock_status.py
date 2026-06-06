from enum import Enum


class DeviceScreenLockStatus(str, Enum):
    SCREENLOCKSTATUSDISABLED = "ScreenLockStatusDisabled"
    SCREENLOCKSTATUSENABLED = "ScreenLockStatusEnabled"
    SCREENLOCKSTATUSUNKNOWN = "ScreenLockStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
