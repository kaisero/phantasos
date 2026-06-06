from .._lenient import LenientStrEnum


class ListDevicesSort(LenientStrEnum):
    DEVICE_BROWSER_VERSION = "device.browser_version"
    DEVICE_FIRST_SEEN = "device.first_seen"
    DEVICE_HOSTNAME = "device.hostname"
    DEVICE_LAST_SEEN = "device.last_seen"
    DEVICE_OS_TYPE = "device.os_type"
    USER_NAME = "user.name"

    def __str__(self) -> str:
        return str(self.value)
