from enum import Enum


class ConcurrentNumberOfDevicesControlType0Action(str, Enum):
    LIMITED = "limited"
    UNLIMITED = "unlimited"

    def __str__(self) -> str:
        return str(self.value)
