from enum import Enum


class NonWebApplicationType(str, Enum):
    NON_WEB = "non-web"

    def __str__(self) -> str:
        return str(self.value)
