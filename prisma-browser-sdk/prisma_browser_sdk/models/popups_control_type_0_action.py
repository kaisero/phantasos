from enum import Enum


class PopupsControlType0Action(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
