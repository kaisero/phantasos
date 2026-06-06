from .._lenient import LenientStrEnum


class UpdateUserGroupBodyUsersItemAction(LenientStrEnum):
    ADD = "add"
    REMOVE = "remove"

    def __str__(self) -> str:
        return str(self.value)
