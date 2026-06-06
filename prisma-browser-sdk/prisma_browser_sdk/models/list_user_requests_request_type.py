from .._lenient import LenientStrEnum


class ListUserRequestsRequestType(LenientStrEnum):
    APPLOGIN = "AppLogin"
    WEBACCESS = "WebAccess"

    def __str__(self) -> str:
        return str(self.value)
