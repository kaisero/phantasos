"""Forward-compatible string enum base (injected by apply_overlay.py).

Generated enum classes are rebased onto LenientStrEnum so that values the live API
returns but the spec doesn't define are accepted (as pseudo-members) instead of
crashing deserialization. Each unexpected value is surfaced once via a warning.
"""

import warnings
from enum import Enum

# Registry of enum values seen at runtime that the spec does not define, keyed by
# enum class name -> set of unexpected values. Useful for sweeping a live tenant to
# discover spec drift (see examples/sweep_get_endpoints.py).
UNKNOWN_ENUM_VALUES: dict[str, set] = {}


class LenientStrEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            UNKNOWN_ENUM_VALUES.setdefault(cls.__name__, set()).add(value)
            warnings.warn(
                f"{cls.__name__}: value {value!r} is not defined in the OpenAPI spec; "
                f"passing it through (the SDK may be out of date)",
                stacklevel=3,
            )
            pseudo = str.__new__(cls, value)
            pseudo._name_ = value
            pseudo._value_ = value
            return pseudo
        return None

    def __str__(self) -> str:
        return str(self.value)
