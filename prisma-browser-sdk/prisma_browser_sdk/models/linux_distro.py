from .._lenient import LenientStrEnum


class LinuxDistro(LenientStrEnum):
    FEDORA = "Fedora"
    IGEL = "Igel"
    UBUNTU = "Ubuntu"

    def __str__(self) -> str:
        return str(self.value)
