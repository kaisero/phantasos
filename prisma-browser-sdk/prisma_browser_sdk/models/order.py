from .._lenient import LenientStrEnum


class Order(LenientStrEnum):
    ASC = "asc"
    DESC = "desc"

    def __str__(self) -> str:
        return str(self.value)
