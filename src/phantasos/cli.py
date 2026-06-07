"""`phantasos build <product>` — load products/<product>/sdk.yml and build its SDK."""

from __future__ import annotations

import argparse
import sys

from .productconfig import load_product


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phantasos")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build an SDK from a product's sdk.yml")
    b.add_argument(
        "product",
        help="product name (products/<name>/sdk.yml) or a path to sdk.yml",
    )
    b.add_argument(
        "--no-smoke",
        action="store_true",
        help="skip the isolated import-check (offline/locked-down builds)",
    )
    args = parser.parse_args(argv)

    if args.cmd == "build":
        from . import build

        try:
            loaded = load_product(args.product)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        result = build(loaded, run_smoke=not args.no_smoke)
        s = result["smoke"]
        pkg = loaded.config.package
        if s.get("skipped"):
            print(f"built {pkg}: smoke skipped; operations: {s['operations']}")
            return 0
        print(
            f"built {pkg}: imported {s['imported']} modules, "
            f"{s['failed']} failures; operations: {s['operations']}"
        )
        for name, err in s["failures"][:10]:
            print("  FAIL", name, err)
        return 1 if s["failed"] else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
