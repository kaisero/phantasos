"""Forward-compatible string-enum base (injected by apply_patches.py).

Generated enum classes are rebased onto LenientStrEnum so a value the live API
returns that the spec does not declare is accepted (as a pseudo-member) instead of
failing validation. Each unexpected value is recorded and surfaced once via a warning.
Pydantic v2 invokes Enum._missing_, so this works for model fields typed as the enum.
"""

import warnings
from enum import Enum

# enum class name -> set of values seen at runtime but absent from the spec.
UNKNOWN_ENUM_VALUES: dict[str, set] = {}


def _record(cls, value):
    UNKNOWN_ENUM_VALUES.setdefault(cls.__name__, set()).add(value)
    warnings.warn(
        f"{cls.__name__}: value {value!r} is not defined in the OpenAPI spec; "
        f"passing it through (the SDK may be out of date)",
        stacklevel=4,
    )


class LenientStrEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            _record(cls, value)
            pseudo = str.__new__(cls, value)
            pseudo._name_ = value
            pseudo._value_ = value
            return pseudo
        return None


class LenientIntEnum(int, Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, int) and not isinstance(value, bool):
            _record(cls, value)
            pseudo = int.__new__(cls, value)
            pseudo._name_ = str(value)
            pseudo._value_ = value
            return pseudo
        return None
