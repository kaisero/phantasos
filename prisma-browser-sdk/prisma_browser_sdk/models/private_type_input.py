from enum import Enum


class PrivateTypeInput(str, Enum):
    PRIVATE = "private"

    def __str__(self) -> str:
        return str(self.value)
