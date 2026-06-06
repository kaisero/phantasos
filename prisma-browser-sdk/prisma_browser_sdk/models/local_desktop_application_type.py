from .._lenient import LenientStrEnum


class LocalDesktopApplicationType(LenientStrEnum):
    LOCALDESKTOPCUSTOM = "localdesktopcustom"

    def __str__(self) -> str:
        return str(self.value)
