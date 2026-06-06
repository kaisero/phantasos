from .._lenient import LenientStrEnum


class DeviceManagementStatus(LenientStrEnum):
    MANAGED = "managed"
    UNMANAGED = "unmanaged"

    def __str__(self) -> str:
        return str(self.value)
