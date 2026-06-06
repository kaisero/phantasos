from enum import Enum


class UserGroupProvider(str, Enum):
    LOCAL = "local"
    SSO = "sso"

    def __str__(self) -> str:
        return str(self.value)
