from enum import Enum


class PluginElementElementType(str, Enum):
    EXCLUDEACCOUNTSHIELD = "excludeAccountShield"
    INCLUDEACCOUNTSHIELD = "includeAccountShield"

    def __str__(self) -> str:
        return str(self.value)
