from .._lenient import LenientStrEnum


class PluginElementElementType(LenientStrEnum):
    EXCLUDEACCOUNTSHIELD = "excludeAccountShield"
    INCLUDEACCOUNTSHIELD = "includeAccountShield"

    def __str__(self) -> str:
        return str(self.value)
