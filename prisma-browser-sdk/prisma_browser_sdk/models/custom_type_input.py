from .._lenient import LenientStrEnum


class CustomTypeInput(LenientStrEnum):
    CUSTOM = "custom"

    def __str__(self) -> str:
        return str(self.value)
