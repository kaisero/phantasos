from enum import Enum


class PolicyPositioningTargetAnchorType(str, Enum):
    RULE = "Rule"
    SECTION = "Section"

    def __str__(self) -> str:
        return str(self.value)
