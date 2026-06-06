from .._lenient import LenientStrEnum


class SectionType(LenientStrEnum):
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
