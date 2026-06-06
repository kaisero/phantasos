from enum import Enum


class MobileManufacturer(str, Enum):
    ASUS = "Asus"
    COOLPAD = "Coolpad"
    GOOGLE = "Google"
    HTC = "HTC"
    HUAWEI = "Huawei"
    INFINIX = "Infinix"
    LENOVO = "Lenovo"
    LG = "LG"
    MEIZU = "Meizu"
    MOTOROLA = "Motorola"
    NOKIA = "Nokia"
    ONEPLUS = "OnePlus"
    OPPO = "Oppo"
    REALME = "Realme"
    SAMSUNG = "Samsung"
    SONY = "Sony"
    TCL = "TCL"
    VIVO = "Vivo"
    XIAOMI = "Xiaomi"
    ZTE = "ZTE"

    def __str__(self) -> str:
        return str(self.value)
