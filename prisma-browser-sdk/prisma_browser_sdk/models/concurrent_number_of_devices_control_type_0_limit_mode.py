from .._lenient import LenientStrEnum


class ConcurrentNumberOfDevicesControlType0LimitMode(LenientStrEnum):
    BYDEVICETYPE = "byDeviceType"
    BYTOTALDEVICES = "byTotalDevices"

    def __str__(self) -> str:
        return str(self.value)
