from enum import Enum


class DeviceGroupPlatform(str, Enum):
    BROWSER_EXTENSION = "Browser Extension"
    CHROMEBOOK = "Chromebook"
    DESKTOP_BROWSER = "Desktop Browser"
    MOBILE_BROWSER = "Mobile Browser"

    def __str__(self) -> str:
        return str(self.value)
