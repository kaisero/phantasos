from .._lenient import LenientStrEnum


class WindowsEdition(LenientStrEnum):
    EDUCATION = "Education"
    ENTERPRISE = "Enterprise"
    HOME = "Home"
    PRO = "Pro"
    SERVER = "Server"

    def __str__(self) -> str:
        return str(self.value)
