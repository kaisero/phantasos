from .._lenient import LenientStrEnum


class CatalogApplicationType(LenientStrEnum):
    CATALOG = "catalog"

    def __str__(self) -> str:
        return str(self.value)
