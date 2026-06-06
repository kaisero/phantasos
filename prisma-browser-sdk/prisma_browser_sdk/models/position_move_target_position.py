from enum import Enum


class PositionMoveTargetPosition(str, Enum):
    AFTER = "after"
    BEFORE = "before"
    BOTTOM = "bottom"
    TOP = "top"

    def __str__(self) -> str:
        return str(self.value)
