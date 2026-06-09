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
    cli_p = sub.add_parser("cli", help="generate / inspect a CLI from a built SDK")
    cli_sub = cli_p.add_subparsers(dest="cli_cmd", required=True)
    disc = cli_sub.add_parser(
        "discover", help="print the classification table + cli.yml stub"
    )
    disc.add_argument(
        "product", help="product name (products/<name>/) or path to sdk.yml"
    )
    disc.add_argument(
        "--write-stub",
        action="store_true",
        help="write products/<name>/cli.yml.stub next to sdk.yml",
    )
    bld = cli_sub.add_parser("build", help="emit the CLI project from a built SDK")
    bld.add_argument(
        "product", help="product name (products/<name>/) or path to sdk.yml"
    )
    args = parser.parse_args(argv)

    if args.cmd == "build":
        from pydantic import ValidationError

        from . import build

        try:
            loaded = load_product(args.product)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        except ValidationError as exc:
            print(f"ERROR: invalid sdk.yml:\n{exc}", file=sys.stderr)
            return 2
        try:
            result = build(loaded, run_smoke=not args.no_smoke)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
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

    if args.cmd == "cli" and args.cli_cmd == "discover":
        from pathlib import Path

        from .generator.cli.classify import build_cli_ir
        from .generator.cli.cliconfig import load_cli_config
        from .generator.cli.discover import render_stub, render_table
        from .generator.cli.introspect import introspect

        try:
            loaded = load_product(args.product)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        try:
            inv = introspect(loaded.config.package, Path(loaded.output_dir))
        except ImportError as exc:
            print(
                f"ERROR: SDK not importable — build it first ({exc})", file=sys.stderr
            )
            return 2
        ir, unmapped = build_cli_ir(inv, cfg)
        print(render_table(ir, unmapped))
        if args.write_stub:
            stub_path = Path(loaded.base_dir) / "cli.yml.stub"
            stub_path.write_text(render_stub(ir, unmapped), encoding="utf-8")
            print(f"\nwrote {stub_path}", file=sys.stderr)
        return 0

    if args.cmd == "cli" and args.cli_cmd == "build":
        from pathlib import Path

        from .generator.cli.classify import build_cli_ir
        from .generator.cli.cliconfig import load_cli_config
        from .generator.cli.introspect import introspect
        from .generator.cli.render_cli import render_cli

        try:
            loaded = load_product(args.product)
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
        try:
            inv = introspect(loaded.config.package, Path(loaded.output_dir))
        except ImportError as exc:
            print(
                f"ERROR: SDK not importable — build it first ({exc})",
                file=sys.stderr,
            )
            return 2
        ir, unmapped = build_cli_ir(inv, cfg)
        cli_pkg = f"{loaded.config.package}_cli"
        out_dir = Path(loaded.output_dir).parent / f"{loaded.config.package}-cli"
        written = render_cli(ir, package=cli_pkg, out_dir=out_dir)
        print(
            f"emitted {len(written)} files to {out_dir} ({len(ir.commands)} commands)"
        )
        if unmapped:
            print(
                f"note: {len(unmapped)} unmapped ops omitted (map in cli.yml)",
                file=sys.stderr,
            )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
