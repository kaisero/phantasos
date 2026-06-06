from .._lenient import LenientStrEnum


class PolicyPositioningTargetAnchorType(LenientStrEnum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
