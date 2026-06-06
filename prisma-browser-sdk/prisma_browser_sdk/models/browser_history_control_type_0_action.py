from .._lenient import LenientStrEnum


class BrowserHistoryControlType0Action(LenientStrEnum):
    DISABLE = "disable"
    ENABLE = "enable"
    PREVENTDELETION = "preventDeletion"

    def __str__(self) -> str:
        return str(self.value)
