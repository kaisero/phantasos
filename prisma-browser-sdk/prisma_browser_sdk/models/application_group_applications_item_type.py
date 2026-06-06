from enum import Enum


class ApplicationGroupApplicationsItemType(str, Enum):
    CATALOG = "catalog"
    CUSTOM = "custom"
    DESKTOP = "desktop"
    NON_WEB = "non-web"
    PRA = "pra"
    PRIVATE = "private"
    USER_NON_WEB = "user-non-web"

    def __str__(self) -> str:
        return str(self.value)
