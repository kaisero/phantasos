from .._lenient import LenientStrEnum


class AllowedOrBlockedExtensionsControlType0RiskLevel(LenientStrEnum):
    HIGH = "high"
    MALICIOUS = "malicious"
    MEDIUM = "medium"

    def __str__(self) -> str:
        return str(self.value)
