from .._lenient import LenientStrEnum


class SignInRuleDetailedActionAction(LenientStrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    PROMPT = "prompt"

    def __str__(self) -> str:
        return str(self.value)
