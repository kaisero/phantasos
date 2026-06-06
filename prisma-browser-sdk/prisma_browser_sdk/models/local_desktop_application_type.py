from enum import Enum


class LocalDesktopApplicationType(str, Enum):
    LOCALDESKTOPCUSTOM = "localdesktopcustom"

    def __str__(self) -> str:
        return str(self.value)
