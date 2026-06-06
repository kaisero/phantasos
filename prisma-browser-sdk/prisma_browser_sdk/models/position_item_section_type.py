from .._lenient import LenientStrEnum


class PositionItemSectionType(LenientStrEnum):
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
