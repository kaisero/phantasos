from .._lenient import LenientStrEnum


class CookiesControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    CLEARONSESSIONEND = "clearOnSessionEnd"

    def __str__(self) -> str:
        return str(self.value)
