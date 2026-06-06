from .._lenient import LenientStrEnum


class DnsOverHttpsControlType0FailureMode(LenientStrEnum):
    BLOCKONFAILURE = "blockOnFailure"
    FALLBACKTOPLAINDNS = "fallbackToPlainDns"

    def __str__(self) -> str:
        return str(self.value)
