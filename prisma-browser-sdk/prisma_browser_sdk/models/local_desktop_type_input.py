from .._lenient import LenientStrEnum


class LocalDesktopTypeInput(LenientStrEnum):
    LOCALDESKTOPCUSTOM = "localdesktopcustom"

    def __str__(self) -> str:
        return str(self.value)
