from .._lenient import LenientStrEnum


class SystemIntegrityPostureStatus(LenientStrEnum):
    FAIL = "fail"
    PASS = "pass"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return str(self.value)
