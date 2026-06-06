from .._lenient import LenientStrEnum


class CsZtaBasicScoreLevel(LenientStrEnum):
    ANY = "Any"
    LOW = "Low"
    MEDIUM = "Medium"
    STRICT = "Strict"
    VERYSTRICT = "VeryStrict"

    def __str__(self) -> str:
        return str(self.value)
