from .._lenient import LenientStrEnum


class BrowserSelfProtectionControlType0Enforcement(LenientStrEnum):
    BLOCK = "block"
    NONE = "none"
    PROMPT = "prompt"

    def __str__(self) -> str:
        return str(self.value)
