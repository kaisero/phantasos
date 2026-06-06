from .._lenient import LenientStrEnum


class PositionMoveTargetPosition(LenientStrEnum):
    AFTER = "after"
    BEFORE = "before"
    BOTTOM = "bottom"
    TOP = "top"

    def __str__(self) -> str:
        return str(self.value)
