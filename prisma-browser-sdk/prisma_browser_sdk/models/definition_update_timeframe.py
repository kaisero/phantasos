from enum import Enum


class DefinitionUpdateTimeframe(str, Enum):
    VALUE_0 = "1 week"
    VALUE_1 = "2 weeks"
    VALUE_2 = "3 weeks"
    VALUE_3 = "1 month"

    def __str__(self) -> str:
        return str(self.value)
