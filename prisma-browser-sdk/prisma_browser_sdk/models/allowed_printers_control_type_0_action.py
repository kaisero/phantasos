from enum import Enum


class AllowedPrintersControlType0Action(str, Enum):
    ALLOWANY = "allowAny"
    ALLOWSPECIFIC = "allowSpecific"

    def __str__(self) -> str:
        return str(self.value)
