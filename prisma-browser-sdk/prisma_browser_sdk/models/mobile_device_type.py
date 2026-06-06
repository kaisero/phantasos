from .._lenient import LenientStrEnum


class MobileDeviceType(LenientStrEnum):
    CHROMEBOOK = "chromebook"
    SMARTPHONE = "smartphone"
    TABLET = "tablet"

    def __str__(self) -> str:
        return str(self.value)
