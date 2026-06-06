from .._lenient import LenientStrEnum


class UserStatus(LenientStrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"

    def __str__(self) -> str:
        return str(self.value)
