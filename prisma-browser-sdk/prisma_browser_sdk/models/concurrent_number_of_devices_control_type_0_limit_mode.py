from enum import Enum


class ConcurrentNumberOfDevicesControlType0LimitMode(str, Enum):
    BYDEVICETYPE = "byDeviceType"
    BYTOTALDEVICES = "byTotalDevices"

    def __str__(self) -> str:
        return str(self.value)
