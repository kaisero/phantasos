from enum import Enum


class MetadataConfigurationVersionType0Status(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
