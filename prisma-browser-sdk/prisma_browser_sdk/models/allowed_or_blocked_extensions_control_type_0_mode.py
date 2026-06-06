from .._lenient import LenientStrEnum


class AllowedOrBlockedExtensionsControlType0Mode(LenientStrEnum):
    ALLOWALL = "allowAll"
    ALLOWBYLIST = "allowByList"
    BLOCKALL = "blockAll"
    BLOCKBYLISTORRISK = "blockByListOrRisk"

    def __str__(self) -> str:
        return str(self.value)
