from .._lenient import LenientStrEnum


class PositionItemRuleType(LenientStrEnum):
    RULE = "Rule"

    def __str__(self) -> str:
        return str(self.value)
