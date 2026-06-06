#!/usr/bin/env python3
"""Smoke-check a generated SDK: import every module and count operations.

    python tools_smoke.py <project_dir> <package_name>

Exits non-zero if any module fails to import.
"""
import importlib
import pkgutil
import re
import sys
from pathlib import Path


def main() -> int:
    project_dir, package = sys.argv[1], sys.argv[2]
    sys.path.insert(0, project_dir)

    pkg = importlib.import_module(package)
    ok = err = 0
    failures = []
    for mod in pkgutil.walk_packages(pkg.__path__, f"{package}."):
        try:
            importlib.import_module(mod.name)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            err += 1
            failures.append((mod.name, repr(exc)[:120]))

    # operation count = public methods on *_api.py classes (excluding variants)
    ops = 0
    for f in sorted((Path(project_dir) / package / "api").glob("*_api.py")):
        for m in re.finditer(r"^    def ([a-z][a-zA-Z0-9_]*)\(", f.read_text(), re.M):
            if not m.group(1).endswith(("_with_http_info", "_without_preload_content")):
                ops += 1

    print(f"imported {ok} modules, {err} failures; operations: {ops}")
    for name, e in failures[:15]:
        print("  FAIL", name, e)
    return 1 if err else 0


if __name__ == "__main__":
    raise SystemExit(main())
