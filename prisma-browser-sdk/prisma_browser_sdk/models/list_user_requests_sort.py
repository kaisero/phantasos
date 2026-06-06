from enum import Enum


class ListUserRequestsSort(str, Enum):
    REQUEST_CREATED_AT = "request.created_at"
    REQUEST_RESPONSE_TIME = "request.response_time"
    REQUEST_STATUS = "request.status"
    REQUEST_TYPE = "request.type"
    REQUEST_URL = "request.url"

    def __str__(self) -> str:
        return str(self.value)
