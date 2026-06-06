from .._lenient import LenientStrEnum


class DeviceOsType(LenientStrEnum):
    ANDROID = "android"
    IOS = "ios"
    LINUX = "linux"
    MACOS = "macOS"
    UNKNOWN = "unknown"
    WINDOWS = "windows"

    def __str__(self) -> str:
        return str(self.value)
