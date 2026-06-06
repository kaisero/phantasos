from .._lenient import LenientStrEnum


class ListApplicationsSort(LenientStrEnum):
    APPLICATION_CREATE_TIME = "application.create_time"
    APPLICATION_ID = "application.id"
    APPLICATION_NAME = "application.name"
    APPLICATION_UPDATE_TIME = "application.update_time"

    def __str__(self) -> str:
        return str(self.value)
