#!/usr/bin/env python3
"""
Idempotent post-generation patches for the OpenAPI Generator (python) output.

OpenAPI Generator has codegen quirks that break the generated package; this
re-applies fixes after every `make generate`. Safe to run repeatedly.

    python apply_patches.py <package_dir>     # e.g. oag-sdk/prisma_browser

Patches:
  1. Apostrophe enum values — values like `'Old McDonald's Farm'` are emitted with
     single quotes and an unescaped inner apostrophe -> SyntaxError. Re-quote them.

(Lenient enums and any further fixups are added in later migration phases.)
"""
import re
import sys
from pathlib import Path

# Enum member whose single-quoted value contains an inner apostrophe.
_APOSTROPHE_ENUM = re.compile(r"^(\s*[A-Z0-9_]+ = )'(.*'.*)'\s*$")

# oneOf deserialization: OAG raises "Multiple matches" when >1 branch validates the
# same payload (common when branches share structure / extra fields are tolerated).
# Make from_json return on the FIRST matching branch instead (the field_validator is
# isinstance-based, so the concrete instance stays unambiguous). Mirrors the prototype.
_ONEOF_FIRST_MATCH = re.compile(
    r"(instance\.actual_instance = \w+\.from_json\(json_str\)\n)(\s*)match \+= 1"
)

# Rebase generated str-enums onto a lenient base so values the live API returns but
# the spec omits (e.g. UserProvider 'scm'/'cie', AuthenticationFactorPinCodeControlMethod
# 'passkey') are accepted instead of raising Pydantic ValidationError. Pydantic v2 honors
# Enum._missing_, so the unknown value is preserved (not mapped to a sentinel) and recorded.
_ENUM_CLASS = re.compile(r"^class (\w+)\(str, Enum\):", re.M)
_ENUM_CLASS_INT = re.compile(r"^class (\w+)\(int, Enum\):", re.M)

LENIENT_SOURCE = '''\
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
'''


def patch_apostrophe_enums(models_dir: Path) -> int:
    fixed = 0
    for path in sorted(models_dir.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        changed = False
        for i, line in enumerate(lines):
            m = _APOSTROPHE_ENUM.match(line)
            if m and '"' not in m.group(2):  # only single-quoted with inner apostrophe
                lines[i] = f'{m.group(1)}"{m.group(2)}"'
                changed = True
                fixed += 1
        if changed:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixed


def rebase_lenient_enums(pkg_dir: Path) -> int:
    """Write _lenient.py and rebase `class X(str, Enum)` -> `class X(LenientStrEnum)`."""
    (pkg_dir / "_lenient.py").write_text(LENIENT_SOURCE, encoding="utf-8")
    pkg_name = pkg_dir.name
    import_line = f"from {pkg_name}._lenient import LenientStrEnum, LenientIntEnum\n"
    rebased = 0
    for path in sorted((pkg_dir / "models").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        has_enum = _ENUM_CLASS.search(text) or _ENUM_CLASS_INT.search(text)
        if not has_enum or "_lenient import" in text:
            continue
        # keep `from enum import Enum` (harmless) and add the lenient import after it
        text = text.replace("from enum import Enum\n", "from enum import Enum\n" + import_line, 1)
        text, n1 = _ENUM_CLASS.subn(r"class \1(LenientStrEnum):", text)
        text, n2 = _ENUM_CLASS_INT.subn(r"class \1(LenientIntEnum):", text)
        path.write_text(text, encoding="utf-8")
        rebased += n1 + n2
    return rebased


def patch_oneof_first_match(models_dir: Path) -> int:
    """oneOf from_json: return on first matching branch instead of raising 'Multiple matches'."""
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


def main() -> int:
    pkg_dir = Path(sys.argv[1])
    models_dir = pkg_dir / "models"
    if not models_dir.is_dir():
        sys.exit(f"ERROR: {models_dir} not found (generate first)")

    n = patch_apostrophe_enums(models_dir)
    print(f"  apostrophe-enum patch: {n} value(s) re-quoted")
    r = rebase_lenient_enums(pkg_dir)
    print(f"  lenient-enum rebase: {r} enum class(es) -> lenient base")
    o = patch_oneof_first_match(models_dir)
    print(f"  oneOf first-match patch: {o} model(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
