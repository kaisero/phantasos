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


def main() -> int:
    pkg_dir = Path(sys.argv[1])
    models_dir = pkg_dir / "models"
    if not models_dir.is_dir():
        sys.exit(f"ERROR: {models_dir} not found (generate first)")

    n = patch_apostrophe_enums(models_dir)
    print(f"  apostrophe-enum patch: {n} value(s) re-quoted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
