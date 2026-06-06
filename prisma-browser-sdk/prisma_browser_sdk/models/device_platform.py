from enum import Enum


class DevicePlatform(str, Enum):
    BROWSER_EXTENSION = "Browser Extension"
    DESKTOP_BROWSER = "Desktop Browser"
    MOBILE_BROWSER = "Mobile Browser"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
