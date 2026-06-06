from .._lenient import LenientStrEnum


class PagesWithInsecureContentControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
