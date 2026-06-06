from enum import Enum


class DeviceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"

    def __str__(self) -> str:
        return str(self.value)
