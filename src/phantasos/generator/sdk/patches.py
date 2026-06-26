"""Generic codegen-bug patches for OpenAPI Generator (python) output.

Spec-agnostic; applied to any generated package. Idempotent.
  - apostrophe enum values (`'Old McDonald's Farm'`) -> re-quoted
  - lenient enums (str+int) -> tolerate values newer than the spec
  - oneOf first-match -> from_json returns the first matching branch
  - oneOf unwrap -> model_dump serializes the wrapper as its actual_instance
  - drop empty additional_properties -> model_dump omits the empty bag
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


def rebase_lenient_enums(pkg_dir: Path, *, package: str | None = None) -> int:
    # `_lenient.py` lives at `<pkg_dir>/_lenient.py`, so the import must carry the
    # FULL dotted import path of the package — for a federated sub-package
    # `prisma_access.objects` that is `prisma_access.objects._lenient`, NOT the leaf
    # `objects._lenient` (which `pkg_dir.name` would yield). Single-spec callers omit
    # `package`, so it defaults to the leaf (unchanged).
    pkg = package or pkg_dir.name
    (pkg_dir / "_lenient.py").write_text(LENIENT_SOURCE, encoding="utf-8")
    import_line = f"from {pkg}._lenient import LenientStrEnum, LenientIntEnum\n"
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


_UNWRAP_METHOD = '''
    @model_serializer
    def _phantasos_unwrap(self) -> Any:
        """phantasos: serialize a oneOf wrapper as its actual instance, so
        model_dump()/model_dump_json() match the hand-written to_dict() instead
        of leaking the generator scaffolding (actual_instance, one_of_schemas, ...)."""
        return self.actual_instance
'''

_DROP_EMPTY_METHOD = '''
    @model_serializer(mode="wrap")
    def _phantasos_drop_empty_additional_properties(self, handler) -> Any:
        """phantasos: omit an empty additional_properties bag from
        model_dump()/model_dump_json(); non-empty bags are left untouched.
        Respects exclude=/by_alias=/exclude_none=, so to_dict() is unchanged."""
        data = handler(self)
        if isinstance(data, dict) and data.get("additional_properties") == {}:
            data.pop("additional_properties")
        return data
'''


def _ensure_model_serializer_import(text: str) -> str:
    # Key on the IMPORT, not a bare `model_serializer` substring, so an unrelated
    # reference (a future field_serializer/model_validator, a hand-edit) can never
    # suppress a needed import while a method still gets injected (-> NameError).
    if "model_serializer," in text or "import model_serializer" in text:
        return text
    return text.replace(
        "from pydantic import ", "from pydantic import model_serializer, ", 1
    )


def patch_oneof_unwrap_serializer(models_dir: Path) -> int:
    """Attach a plain model_serializer to each oneOf wrapper so model_dump unwraps."""
    count = 0
    for path in sorted(models_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "actual_instance" not in text or "one_of_schemas" not in text:
            continue
        if "_phantasos_unwrap" in text:
            continue  # idempotent
        if "\n    def to_str(self)" not in text:
            continue  # anchor absent (OAG changed) — skip, don't write unchanged
        text = _ensure_model_serializer_import(text)
        text = text.replace(
            "\n    def to_str(self)", _UNWRAP_METHOD + "\n    def to_str(self)", 1
        )
        path.write_text(text, encoding="utf-8")
        count += 1
    return count


def patch_drop_empty_additional_properties(models_dir: Path) -> int:
    """Attach a wrap model_serializer dropping empty additional_properties bags.

    Skips oneOf wrappers (they carry no additional_properties field and get the
    unwrap serializer instead); a class may have at most one model_serializer.
    """
    count = 0
    for path in sorted(models_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "additional_properties: Dict[str, Any] = {}" not in text:
            continue
        if "one_of_schemas" in text:
            continue  # belongs to the unwrap patch
        if "_phantasos_drop_empty_additional_properties" in text:
            continue  # idempotent
        if "\n    def to_str(self)" not in text:
            continue  # anchor absent (OAG changed) — skip, don't write unchanged
        text = _ensure_model_serializer_import(text)
        text = text.replace(
            "\n    def to_str(self)", _DROP_EMPTY_METHOD + "\n    def to_str(self)", 1
        )
        path.write_text(text, encoding="utf-8")
        count += 1
    return count


def apply_generic_patches(
    pkg_dir: Path, *, package: str | None = None
) -> dict[str, int]:
    models = pkg_dir / "models"
    return {
        "apostrophe": patch_apostrophe_enums(models),
        "lenient_enums": rebase_lenient_enums(pkg_dir, package=package),
        "oneof_first_match": patch_oneof_first_match(models),
        "oneof_unwrap": patch_oneof_unwrap_serializer(models),
        "drop_empty_additional_properties": patch_drop_empty_additional_properties(
            models
        ),
    }
