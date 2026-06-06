from .._lenient import LenientStrEnum


class OpenLinksInExternalAppsControlType0Action(LenientStrEnum):
    ALLOWSPECIFICAPPS = "allowSpecificApps"
    ALWAYSALLOW = "alwaysAllow"
    ALWAYSBLOCK = "alwaysBlock"
    ASKUSER = "askUser"

    def __str__(self) -> str:
        return str(self.value)
