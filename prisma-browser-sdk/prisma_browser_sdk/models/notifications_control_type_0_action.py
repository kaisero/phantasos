from .._lenient import LenientStrEnum


class NotificationsControlType0Action(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"

    def __str__(self) -> str:
        return str(self.value)
