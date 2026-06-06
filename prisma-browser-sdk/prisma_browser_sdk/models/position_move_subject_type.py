from .._lenient import LenientStrEnum


class PositionMoveSubjectType(LenientStrEnum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
