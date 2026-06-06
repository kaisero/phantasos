from .._lenient import LenientStrEnum


class BrowserBrand(LenientStrEnum):
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
