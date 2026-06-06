from .._lenient import LenientStrEnum


class ExternalApplicationLaunchExceptionAction(LenientStrEnum):
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
