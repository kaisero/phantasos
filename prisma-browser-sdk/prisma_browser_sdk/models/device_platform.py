from .._lenient import LenientStrEnum


class DevicePlatform(LenientStrEnum):
    BROWSER_EXTENSION = "Browser Extension"
    DESKTOP_BROWSER = "Desktop Browser"
    MOBILE_BROWSER = "Mobile Browser"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
