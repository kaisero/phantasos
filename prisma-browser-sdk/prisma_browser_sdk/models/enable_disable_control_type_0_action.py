from enum import Enum


class EnableDisableControlType0Action(str, Enum):
    DISABLE = "disable"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
