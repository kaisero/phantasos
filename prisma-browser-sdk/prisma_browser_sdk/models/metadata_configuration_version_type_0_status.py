from .._lenient import LenientStrEnum


class MetadataConfigurationVersionType0Status(LenientStrEnum):
    ACTIVE = "active"
    DRAFT = "draft"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
