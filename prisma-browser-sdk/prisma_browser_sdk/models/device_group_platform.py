from .._lenient import LenientStrEnum


class DeviceGroupPlatform(LenientStrEnum):
    BROWSER_EXTENSION = "Browser Extension"
    CHROMEBOOK = "Chromebook"
    DESKTOP_BROWSER = "Desktop Browser"
    MOBILE_BROWSER = "Mobile Browser"

    def __str__(self) -> str:
        return str(self.value)
