from enum import Enum


class LocalDesktopTypeInput(str, Enum):
    LOCALDESKTOPCUSTOM = "localdesktopcustom"

    def __str__(self) -> str:
        return str(self.value)
