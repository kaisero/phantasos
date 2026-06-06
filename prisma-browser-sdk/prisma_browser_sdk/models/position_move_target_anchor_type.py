from .._lenient import LenientStrEnum


class PositionMoveTargetAnchorType(LenientStrEnum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
