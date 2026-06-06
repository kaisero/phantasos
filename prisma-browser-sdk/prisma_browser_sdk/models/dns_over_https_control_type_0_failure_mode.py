from enum import Enum


class DnsOverHttpsControlType0FailureMode(str, Enum):
    BLOCKONFAILURE = "blockOnFailure"
    FALLBACKTOPLAINDNS = "fallbackToPlainDns"

    def __str__(self) -> str:
        return str(self.value)
