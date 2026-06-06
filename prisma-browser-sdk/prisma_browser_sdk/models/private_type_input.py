from .._lenient import LenientStrEnum


class PrivateTypeInput(LenientStrEnum):
    PRIVATE = "private"

    def __str__(self) -> str:
        return str(self.value)
