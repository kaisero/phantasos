"""Generic codegen-bug patches for OpenAPI Generator (python) output.

Spec-agnostic; applied to any generated package. Idempotent.
  - apostrophe enum values (`'Old McDonald's Farm'`) -> re-quoted
  - lenient enums (str+int) -> tolerate values newer than the spec
  - oneOf first-match -> from_json returns the first matching branch
"""

from __future__ import annotations

import re
from pathlib import Path

_APOSTROPHE_ENUM = re.compile(r"^(\s*[A-Z0-9_]+ = )'(.*'.*)'\s*$")
_ENUM_CLASS = re.compile(r"^class (\w+)\(str, Enum\):", re.M)
_ENUM_CLASS_INT = re.compile(r"^class (\w+)\(int, Enum\):", re.M)
_ONEOF_FIRST_MATCH = re.compile(
    r"(instance\.actual_instance = \w+\.from_json\(json_str\)\n)(\s*)match \+= 1"
)

LENIENT_SOURCE = '''\
"""Forward-compatible string/int enum base (injected by phantasos).

Generated enums are rebased onto these so values the live API returns that the spec
does not declare are accepted (as pseudo-members) instead of failing validation.
Pydantic v2 invokes Enum._missing_, so this works for model fields typed as the enum.
"""

import warnings
from enum import Enum

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
'''


def patch_apostrophe_enums(models_dir: Path) -> int:
    fixed = 0
    for path in sorted(models_dir.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for i, line in enumerate(lines):
            m = _APOSTROPHE_ENUM.match(line)
            if m and '"' not in m.group(2):
                lines[i] = f'{m.group(1)}"{m.group(2)}"'
                changed = True
                fixed += 1
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixed


def rebase_lenient_enums(pkg_dir: Path) -> int:
    (pkg_dir / "_lenient.py").write_text(LENIENT_SOURCE, encoding="utf-8")
    import_line = (
        f"from {pkg_dir.name}._lenient import LenientStrEnum, LenientIntEnum\n"
    )
    rebased = 0
    for path in sorted((pkg_dir / "models").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if (
            not (_ENUM_CLASS.search(text) or _ENUM_CLASS_INT.search(text))
            or "_lenient import" in text
        ):
            continue
        text = text.replace(
            "from enum import Enum\n", "from enum import Enum\n" + import_line, 1
        )
        text, n1 = _ENUM_CLASS.subn(r"class \1(LenientStrEnum):", text)
        text, n2 = _ENUM_CLASS_INT.subn(r"class \1(LenientIntEnum):", text)
        path.write_text(text, encoding="utf-8")
        rebased += n1 + n2
    return rebased


def patch_oneof_first_match(models_dir: Path) -> int:
    files = 0
    for path in sorted(models_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "actual_instance = " not in text or "from_json(json_str)" not in text:
            continue
        new_text, k = _ONEOF_FIRST_MATCH.subn(r"\1\2return instance", text)
        if k:
            path.write_text(new_text, encoding="utf-8")
            files += 1
    return files


def apply_generic_patches(pkg_dir: Path) -> dict[str, int]:
    models = pkg_dir / "models"
    return {
        "apostrophe": patch_apostrophe_enums(models),
        "lenient_enums": rebase_lenient_enums(pkg_dir),
        "oneof_first_match": patch_oneof_first_match(models),
    }
