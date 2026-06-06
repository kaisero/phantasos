from enum import Enum


class WindowsEdition(str, Enum):
    EDUCATION = "Education"
    ENTERPRISE = "Enterprise"
    HOME = "Home"
    PRO = "Pro"
    SERVER = "Server"

    def __str__(self) -> str:
        return str(self.value)
