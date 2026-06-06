from .._lenient import LenientStrEnum


class PopupsControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
