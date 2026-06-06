from .._lenient import LenientStrEnum


class LaunchingExternalApplicationsControlType0Action(LenientStrEnum):
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
