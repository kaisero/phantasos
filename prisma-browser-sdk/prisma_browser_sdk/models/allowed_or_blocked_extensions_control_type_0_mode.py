from enum import Enum


class AllowedOrBlockedExtensionsControlType0Mode(str, Enum):
    ALLOWALL = "allowAll"
    ALLOWBYLIST = "allowByList"
    BLOCKALL = "blockAll"
    BLOCKBYLISTORRISK = "blockByListOrRisk"

    def __str__(self) -> str:
        return str(self.value)
