from enum import Enum


class ExternalApplicationLaunchExceptionAction(str, Enum):
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
