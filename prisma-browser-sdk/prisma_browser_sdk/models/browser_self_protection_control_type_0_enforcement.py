from enum import Enum


class BrowserSelfProtectionControlType0Enforcement(str, Enum):
    BLOCK = "block"
    NONE = "none"
    PROMPT = "prompt"

    def __str__(self) -> str:
        return str(self.value)
