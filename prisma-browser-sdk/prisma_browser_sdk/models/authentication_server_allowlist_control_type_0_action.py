from enum import Enum


class AuthenticationServerAllowlistControlType0Action(str, Enum):
    ALLOWLIST = "allowList"
    UNSET = "unset"

    def __str__(self) -> str:
        return str(self.value)
