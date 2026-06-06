from enum import Enum


class PostQuantumKeySecurityControlType0Action(str, Enum):
    DEFAULT = "default"
    DISABLE = "disable"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
