from enum import Enum


class PositionMoveSubjectType(str, Enum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
