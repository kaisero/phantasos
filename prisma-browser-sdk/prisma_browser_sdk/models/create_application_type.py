from .._lenient import LenientStrEnum


class CreateApplicationType(LenientStrEnum):
    CATALOG = "catalog"
    CUSTOM = "custom"
    LOCALDESKTOPCUSTOM = "localdesktopcustom"
    NON_WEB = "non-web"
    PRIVATE = "private"

    def __str__(self) -> str:
        return str(self.value)
