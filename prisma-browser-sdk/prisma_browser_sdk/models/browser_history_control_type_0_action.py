from enum import Enum


class BrowserHistoryControlType0Action(str, Enum):
    DISABLE = "disable"
    ENABLE = "enable"
    PREVENTDELETION = "preventDeletion"

    def __str__(self) -> str:
        return str(self.value)
