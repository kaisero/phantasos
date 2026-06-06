from enum import Enum


class BrowserBrand(str, Enum):
    ARC = "Arc"
    BRAVE = "Brave"
    CHROME = "Chrome"
    COMET = "Comet"
    DIA = "Dia"
    EDGE = "Edge"
    OPERA = "Opera"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
