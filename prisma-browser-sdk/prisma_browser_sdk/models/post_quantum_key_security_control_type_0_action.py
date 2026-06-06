from .._lenient import LenientStrEnum


class PostQuantumKeySecurityControlType0Action(LenientStrEnum):
    DEFAULT = "default"
    DISABLE = "disable"
    ENABLE = "enable"

    def __str__(self) -> str:
        return str(self.value)
