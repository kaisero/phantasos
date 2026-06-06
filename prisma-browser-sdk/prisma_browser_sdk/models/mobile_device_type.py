from enum import Enum


class MobileDeviceType(str, Enum):
    CHROMEBOOK = "chromebook"
    SMARTPHONE = "smartphone"
    TABLET = "tablet"

    def __str__(self) -> str:
        return str(self.value)
