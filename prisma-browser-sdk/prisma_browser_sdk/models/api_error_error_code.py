from .._lenient import LenientStrEnum


class ApiErrorErrorCode(LenientStrEnum):
    CONFLICT = "CONFLICT"
    CONTIGUITY_VIOLATION = "CONTIGUITY_VIOLATION"
    FORBIDDEN = "FORBIDDEN"
    INCOMPLETE_ARRAY = "INCOMPLETE_ARRAY"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    def __str__(self) -> str:
        return str(self.value)
