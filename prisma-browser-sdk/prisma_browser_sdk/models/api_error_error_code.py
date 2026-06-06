from enum import Enum


class ApiErrorErrorCode(str, Enum):
    CONFLICT = "CONFLICT"
    CONTIGUITY_VIOLATION = "CONTIGUITY_VIOLATION"
    FORBIDDEN = "FORBIDDEN"
    INCOMPLETE_ARRAY = "INCOMPLETE_ARRAY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    def __str__(self) -> str:
        return str(self.value)
