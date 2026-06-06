from .._lenient import LenientStrEnum


class ListUserRequestsRequestStatus(LenientStrEnum):
    APPROVED = "Approved"
    DECLINED = "Declined"
    PENDING = "Pending"
    REVOKED = "Revoked"

    def __str__(self) -> str:
        return str(self.value)
