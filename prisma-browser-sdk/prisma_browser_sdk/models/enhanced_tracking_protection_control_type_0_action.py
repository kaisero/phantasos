from .._lenient import LenientStrEnum


class EnhancedTrackingProtectionControlType0Action(LenientStrEnum):
    DISABLE = "disable"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
