from enum import Enum


class RequestActionAction(str, Enum):
    APPROVE = "approve"
    DECLINE = "decline"

    def __str__(self) -> str:
        return str(self.value)
