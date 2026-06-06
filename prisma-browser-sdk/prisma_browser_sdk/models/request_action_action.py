from .._lenient import LenientStrEnum


class RequestActionAction(LenientStrEnum):
    APPROVE = "approve"
    DECLINE = "decline"

    def __str__(self) -> str:
        return str(self.value)
