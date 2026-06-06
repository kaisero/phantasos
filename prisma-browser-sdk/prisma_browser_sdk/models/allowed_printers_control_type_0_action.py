from .._lenient import LenientStrEnum


class AllowedPrintersControlType0Action(LenientStrEnum):
    ALLOWANY = "allowAny"
    ALLOWSPECIFIC = "allowSpecific"

    def __str__(self) -> str:
        return str(self.value)
