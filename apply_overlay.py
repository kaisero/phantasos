#!/usr/bin/env python3
"""
Post-generation step: make the generated SDK whole again after a regenerate.

Idempotent. Run after `openapi-python-client generate`. Safe to run repeatedly.

1. Copy the hand-written overlay (``overlay/``) into the generated package as
   ``prisma_browser_sdk/extras/``. The destination is fully replaced each run so
   it always matches source (no stale files), and it survives `--overwrite`
   because the generator only rewrites files it owns.
2. Patch the generator's ``cast`` collision: any model module that *calls*
   ``cast(...)`` (typing.cast) but never imports it — because a schema property is
   literally named ``cast`` and shadows it — would crash at runtime. We alias the
   import (``cast as _typing_cast``) and rewrite the call sites. Detection keys on
   the actual defect, so it also catches future same-shaped collisions.

Stdlib only — no third-party deps, so it runs under any Python the build uses.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OVERLAY_SRC = ROOT / "overlay"
PACKAGE = ROOT / "prisma-browser-sdk" / "prisma_browser_sdk"
EXTRAS_DST = PACKAGE / "extras"
MODELS_DIR = PACKAGE / "models"
LENIENT_MODULE = PACKAGE / "_lenient.py"

# A str-Enum base that tolerates values newer than the spec. The live API returns
# enum values (e.g. UserProvider "scm") that the spec omits; with the stock
# `class X(str, Enum)` these raise ValueError and fail to parse the whole response.
# Lenient parsing keeps the response usable while surfacing the drift via a warning.
LENIENT_SOURCE = '''\
"""Forward-compatible string enum base (injected by apply_overlay.py).

Generated enum classes are rebased onto LenientStrEnum so that values the live API
returns but the spec doesn't define are accepted (as pseudo-members) instead of
crashing deserialization. Each unexpected value is surfaced once via a warning.
"""

import warnings
from enum import Enum


class LenientStrEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
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
'''

ENUM_CLASS = re.compile(r"class (\w+)\(str, Enum\):")

# A typing.cast call: `cast(` not preceded by a word char or dot (so it never
# matches `self.cast(`, `_typing_cast(`, or an attribute access).
CAST_CALL = re.compile(r"(?<![\w.])cast\(")
# Does the file already import cast from typing (plain or aliased)?
IMPORTS_CAST = re.compile(r"^from typing import .*\bcast\b", re.MULTILINE)
FIRST_TYPING_IMPORT = re.compile(r"^(from typing import .*\n)", re.MULTILINE)
ALIAS_IMPORT = "from typing import cast as _typing_cast\n"


def copy_overlay() -> None:
    if not OVERLAY_SRC.is_dir():
        sys.exit(f"ERROR: overlay source not found: {OVERLAY_SRC}")
    if not PACKAGE.is_dir():
        sys.exit(f"ERROR: generated package not found: {PACKAGE} (generate first)")
    if EXTRAS_DST.exists():
        shutil.rmtree(EXTRAS_DST)
    shutil.copytree(OVERLAY_SRC, EXTRAS_DST, ignore=shutil.ignore_patterns("__pycache__"))
    n = len(list(EXTRAS_DST.glob("*.py")))
    print(f"  overlay -> {EXTRAS_DST.relative_to(ROOT)} ({n} modules)")


def patch_cast_collisions() -> None:
    patched = []
    for path in sorted(MODELS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        # Defect = calls cast(...) but does not import cast. Files that import it
        # have no shadowing property and already work, so leave them untouched.
        if not CAST_CALL.search(text) or IMPORTS_CAST.search(text):
            continue
        new_text = CAST_CALL.sub("_typing_cast(", text)
        if FIRST_TYPING_IMPORT.search(new_text):
            new_text = FIRST_TYPING_IMPORT.sub(lambda m: m.group(1) + ALIAS_IMPORT, new_text, count=1)
        else:
            new_text = ALIAS_IMPORT + new_text
        path.write_text(new_text, encoding="utf-8")
        patched.append(path.name)
    if patched:
        print(f"  cast-collision patched: {', '.join(patched)}")
    else:
        print("  cast-collision patch: nothing to do (already clean)")


def patch_lenient_enums() -> None:
    LENIENT_MODULE.write_text(LENIENT_SOURCE, encoding="utf-8")
    patched = 0
    for path in sorted(MODELS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if not ENUM_CLASS.search(text):
            continue
        if "_lenient import LenientStrEnum" in text:  # already patched
            continue
        text = text.replace(
            "from enum import Enum", "from .._lenient import LenientStrEnum"
        )
        text = ENUM_CLASS.sub(r"class \1(LenientStrEnum):", text)
        path.write_text(text, encoding="utf-8")
        patched += 1
    print(f"  lenient-enum rebased: {patched} enum module(s); base at {LENIENT_MODULE.relative_to(ROOT)}")


def main() -> None:
    print("[overlay] copying conveniences")
    copy_overlay()
    print("[overlay] patching generator cast() collisions")
    patch_cast_collisions()
    print("[overlay] rebasing enums onto LenientStrEnum")
    patch_lenient_enums()
    print("[overlay] done")


if __name__ == "__main__":
    main()
