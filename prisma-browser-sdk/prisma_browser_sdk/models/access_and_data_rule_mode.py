from enum import Enum


class AccessAndDataRuleMode(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    MONITOR = "monitor"

    def __str__(self) -> str:
        return str(self.value)
