from enum import Enum


class RuleSummaryType(str, Enum):
    RULE = "Rule"

    def __str__(self) -> str:
        return str(self.value)
