from enum import Enum


class AllowedOrBlockedExtensionsControlType0RiskLevel(str, Enum):
    HIGH = "high"
    MALICIOUS = "malicious"
    MEDIUM = "medium"

    def __str__(self) -> str:
        return str(self.value)
