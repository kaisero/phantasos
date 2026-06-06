from enum import Enum


class SectionType(str, Enum):
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
