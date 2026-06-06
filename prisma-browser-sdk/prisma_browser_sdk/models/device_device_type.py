from enum import Enum


class DeviceDeviceType(str, Enum):
    CHROMEBOOK = "chromebook"
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    SMARTPHONE = "smartphone"
    TABLET = "tablet"
    UNKNOWN = "unknown"
    VM = "vm"

    def __str__(self) -> str:
        return str(self.value)
