from enum import Enum


class CatalogApplicationType(str, Enum):
    CATALOG = "catalog"

    def __str__(self) -> str:
        return str(self.value)
