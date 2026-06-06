from enum import Enum


class SignInRuleDetailedActionAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    PROMPT = "prompt"

    def __str__(self) -> str:
        return str(self.value)
