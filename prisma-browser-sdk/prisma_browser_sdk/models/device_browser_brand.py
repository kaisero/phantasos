from .._lenient import LenientStrEnum


class DeviceBrowserBrand(LenientStrEnum):
    ARC = "Arc"
    BRAVE = "Brave"
    CHROME = "Chrome"
    COMET = "Comet"
    DIA = "Dia"
    EDGE = "Edge"
    OPERA = "Opera"
    PRISMA_BROWSER = "Prisma Browser"
    UNKNOWN = "Unknown"

    def __str__(self) -> str:
        return str(self.value)
