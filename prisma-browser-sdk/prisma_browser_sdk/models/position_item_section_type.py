from enum import Enum


class PositionItemSectionType(str, Enum):
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
