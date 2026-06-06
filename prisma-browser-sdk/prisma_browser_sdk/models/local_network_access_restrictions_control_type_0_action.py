from .._lenient import LenientStrEnum


class LocalNetworkAccessRestrictionsControlType0Action(LenientStrEnum):
    DISABLE = "disable"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
