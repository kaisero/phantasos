from .._lenient import LenientStrEnum


class DeviceScreenLockStatus(LenientStrEnum):
    SCREENLOCKSTATUSDISABLED = "ScreenLockStatusDisabled"
    SCREENLOCKSTATUSENABLED = "ScreenLockStatusEnabled"
    SCREENLOCKSTATUSUNKNOWN = "ScreenLockStatusUnknown"

    def __str__(self) -> str:
        return str(self.value)
