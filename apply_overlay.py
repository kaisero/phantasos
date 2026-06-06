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


def main() -> None:
    print("[overlay] copying conveniences")
    copy_overlay()
    print("[overlay] patching generator cast() collisions")
    patch_cast_collisions()
    print("[overlay] done")


if __name__ == "__main__":
    main()
