from .._lenient import LenientStrEnum


class DeviceManufacturer(LenientStrEnum):
    ACER = "Acer"
    APPLE = "Apple"
    ASUS = "Asus"
    DELL = "Dell"
    HP = "HP"
    LENOVO = "Lenovo"
    MICROSOFT = "Microsoft"
    TOSHIBA = "Toshiba"

    def __str__(self) -> str:
        return str(self.value)
