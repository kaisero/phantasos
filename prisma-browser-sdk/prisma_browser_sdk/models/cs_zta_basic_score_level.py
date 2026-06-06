from enum import Enum


class CsZtaBasicScoreLevel(str, Enum):
    ANY = "Any"
    LOW = "Low"
    MEDIUM = "Medium"
    STRICT = "Strict"
    VERYSTRICT = "VeryStrict"

    def __str__(self) -> str:
        return str(self.value)
