from enum import Enum


class SystemIntegrityPostureStatus(str, Enum):
    FAIL = "fail"
    PASS = "pass"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return str(self.value)
