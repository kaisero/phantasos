from .._lenient import LenientStrEnum


class DeviceStatus(LenientStrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"

    def __str__(self) -> str:
        return str(self.value)
