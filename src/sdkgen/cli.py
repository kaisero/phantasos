"""`sdkgen build <config>` — load a spec's config module and build its SDK."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _load_spec_module(config_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("_sdk_config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec config module from {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdkgen")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build an SDK from a spec's config module")
    b.add_argument(
        "config",
        help="path to the spec config module, e.g. transformations/<product>.py",
    )
    args = parser.parse_args(argv)

    if args.cmd == "build":
        from . import build

        config_path = Path(args.config).resolve()
        if not config_path.exists():
            print(f"ERROR: {config_path} not found", file=sys.stderr)
            return 2
        # resolve relative paths (spec=) against the config's directory
        import os

        cwd = Path.cwd()
        os.chdir(config_path.parent)
        try:
            mod = _load_spec_module(config_path)
            result = build(
                mod.CONFIG,
                preprocess_hook=getattr(mod, "preprocess", None),
                patch_hook=getattr(mod, "patch", None),
            )
        finally:
            os.chdir(cwd)
        s = result["smoke"]
        print(
            f"built {mod.CONFIG.package}: imported {s['imported']} modules, "
            f"{s['failed']} failures; operations: {s['operations']}"
        )
        for name, err in s["failures"][:10]:
            print("  FAIL", name, err)
        return 1 if s["failed"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
