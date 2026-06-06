from .._lenient import LenientStrEnum


class UserGroupProvider(LenientStrEnum):
    LOCAL = "local"
    SSO = "sso"

    def __str__(self) -> str:
        return str(self.value)
