from enum import Enum


class CookiesControlType0Action(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    CLEARONSESSIONEND = "clearOnSessionEnd"

    def __str__(self) -> str:
        return str(self.value)
