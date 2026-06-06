"""Smoke check: import every generated module and count operations."""

from __future__ import annotations

import importlib
import pkgutil
import re
import sys
from pathlib import Path


def smoke(project_dir: str, package: str) -> dict:
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
            failures.append((mod.name, repr(exc)[:160]))
    ops = 0
    for f in sorted((Path(project_dir) / package / "api").glob("*_api.py")):
        for m in re.finditer(r"^    def ([a-z][a-zA-Z0-9_]*)\(", f.read_text(), re.M):
            if not m.group(1).endswith(("_with_http_info", "_without_preload_content")):
                ops += 1
    return {"imported": ok, "failed": err, "operations": ops, "failures": failures}
