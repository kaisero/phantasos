from .._lenient import LenientStrEnum


class ListApplicationGroupsSort(LenientStrEnum):
    APPLICATION_GROUP_CREATE_TIME = "application_group.create_time"
    APPLICATION_GROUP_ID = "application_group.id"
    APPLICATION_GROUP_NAME = "application_group.name"
    APPLICATION_GROUP_UPDATE_TIME = "application_group.update_time"

    def __str__(self) -> str:
        return str(self.value)
