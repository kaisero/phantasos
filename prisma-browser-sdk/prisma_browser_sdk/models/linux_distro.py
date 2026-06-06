from enum import Enum


class LinuxDistro(str, Enum):
    FEDORA = "Fedora"
    IGEL = "Igel"
    UBUNTU = "Ubuntu"

    def __str__(self) -> str:
        return str(self.value)
