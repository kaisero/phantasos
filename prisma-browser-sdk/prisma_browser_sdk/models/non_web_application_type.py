from .._lenient import LenientStrEnum


class NonWebApplicationType(LenientStrEnum):
    NON_WEB = "non-web"

    def __str__(self) -> str:
        return str(self.value)
