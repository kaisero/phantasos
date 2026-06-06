from .._lenient import LenientStrEnum


class PolicyPositioningTargetPosition(LenientStrEnum):
    AFTER = "after"
    BEFORE = "before"
    BOTTOM = "bottom"
    TOP = "top"

    def __str__(self) -> str:
        return str(self.value)
