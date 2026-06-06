from .._lenient import LenientStrEnum


class AuthenticationServerAllowlistControlType0Action(LenientStrEnum):
    ALLOWLIST = "allowList"
    UNSET = "unset"

    def __str__(self) -> str:
        return str(self.value)
