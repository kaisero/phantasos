from enum import Enum


class PositionItemRuleType(str, Enum):
    RULE = "Rule"

    def __str__(self) -> str:
        return str(self.value)
