from .._lenient import LenientStrEnum


class CustomApplicationType(LenientStrEnum):
    CUSTOM = "custom"

    def __str__(self) -> str:
        return str(self.value)
