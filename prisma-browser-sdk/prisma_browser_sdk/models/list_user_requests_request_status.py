from enum import Enum


class ListUserRequestsRequestStatus(str, Enum):
    APPROVED = "Approved"
    DECLINED = "Declined"
    PENDING = "Pending"
    REVOKED = "Revoked"

    def __str__(self) -> str:
        return str(self.value)
