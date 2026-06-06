from enum import Enum


class ListUserRequestsRequestType(str, Enum):
    APPLOGIN = "AppLogin"
    WEBACCESS = "WebAccess"

    def __str__(self) -> str:
        return str(self.value)
