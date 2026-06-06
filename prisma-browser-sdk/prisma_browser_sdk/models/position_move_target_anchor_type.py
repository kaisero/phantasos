from enum import Enum


class PositionMoveTargetAnchorType(str, Enum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
