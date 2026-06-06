from enum import Enum


class LaunchingExternalApplicationsControlType0Action(str, Enum):
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
