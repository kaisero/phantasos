from .._lenient import LenientStrEnum


class PrivateApplicationType(LenientStrEnum):
    PRIVATE = "private"

    def __str__(self) -> str:
        return str(self.value)
