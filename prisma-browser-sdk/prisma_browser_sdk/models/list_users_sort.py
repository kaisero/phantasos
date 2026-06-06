from .._lenient import LenientStrEnum


class ListUsersSort(LenientStrEnum):
    USER_EMAIL = "user.email"
    USER_FIRST_SEEN = "user.first_seen"
    USER_LAST_SEEN = "user.last_seen"
    USER_NAME = "user.name"
    USER_STATUS = "user.status"

    def __str__(self) -> str:
        return str(self.value)
