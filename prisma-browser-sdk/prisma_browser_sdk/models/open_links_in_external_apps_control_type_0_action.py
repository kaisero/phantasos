from enum import Enum


class OpenLinksInExternalAppsControlType0Action(str, Enum):
    ALLOWSPECIFICAPPS = "allowSpecificApps"
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
