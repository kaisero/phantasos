from .._lenient import LenientStrEnum


class RuleMode(LenientStrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    MONITOR = "monitor"

    def __str__(self) -> str:
        return str(self.value)
