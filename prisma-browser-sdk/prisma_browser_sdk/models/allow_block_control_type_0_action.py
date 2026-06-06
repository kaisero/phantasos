from .._lenient import LenientStrEnum


class AllowBlockControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
