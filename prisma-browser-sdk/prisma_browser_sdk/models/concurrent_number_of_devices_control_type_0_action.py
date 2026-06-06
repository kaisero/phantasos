from .._lenient import LenientStrEnum


class ConcurrentNumberOfDevicesControlType0Action(LenientStrEnum):
    LIMITED = "limited"
    UNLIMITED = "unlimited"

    def __str__(self) -> str:
        return str(self.value)
