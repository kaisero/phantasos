from enum import Enum


class DeviceManufacturer(str, Enum):
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
