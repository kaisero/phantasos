from enum import Enum


class PrivateApplicationType(str, Enum):
    PRIVATE = "private"

    def __str__(self) -> str:
        return str(self.value)
