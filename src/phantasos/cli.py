"""phantasos host CLI: `sdk build`, `cli discover`, `cli build`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from .productconfig import load_product

if TYPE_CHECKING:
    from .generator.cli.cliconfig import CliConfig
    from .generator.cli.ir import CliIR
    from .productconfig import LoadedProduct

app = typer.Typer(no_args_is_help=True, add_completion=False)
sdk_app = typer.Typer(no_args_is_help=True)
cli_app = typer.Typer(no_args_is_help=True)
app.add_typer(sdk_app, name="sdk", help="build SDKs from a product's sdk.yml")
app.add_typer(cli_app, name="cli", help="generate / inspect a CLI from a built SDK")


def _load_or_exit(product: str) -> LoadedProduct:
    try:
        return load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc


def _build_ir_or_exit(loaded: LoadedProduct) -> tuple[CliIR, CliConfig, list[str]]:
    from .generator.cli.classify import build_ir
    from .generator.cli.cliconfig import load_cli_config

    cfg = load_cli_config(Path(loaded.base_dir) / "cli.yml")
    try:
        # build_ir detects a federated SDK (`_SUBPACKAGES` on the top-level
        # package), introspects each sub, and merges into one CliIR (commands
        # stamped with their slug). A single-spec SDK keeps the unchanged path.
        # Either way the command tree is classified off the RAW operation names
        # and dispatch goes through the typed client.<object>.<verb>(...) wrappers.
        ir, unmapped = build_ir(loaded.config.package, Path(loaded.output_dir), cfg)
    except ImportError as exc:
        typer.echo(f"ERROR: SDK not importable — build it first ({exc})", err=True)
        raise typer.Exit(2) from exc
    return ir, cfg, unmapped


@sdk_app.command("build")
def sdk_build(
    product: str = typer.Argument(
        ..., help="product name (products/<name>/sdk.yml) or a path to sdk.yml"
    ),
    no_smoke: bool = typer.Option(
        False,
        "--no-smoke",
        help="skip the isolated import-check (offline/locked-down builds)",
    ),
) -> None:
    """build an SDK from a product's sdk.yml"""
    from pydantic import ValidationError

    from .generator.sdk import build

    try:
        loaded = load_product(product)
    except (FileNotFoundError, ValueError) as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc
    except ValidationError as exc:
        typer.echo(f"ERROR: invalid sdk.yml:\n{exc}", err=True)
        raise typer.Exit(2) from exc
    try:
        result = build(loaded, run_smoke=not no_smoke)
    except ValueError as exc:
        typer.echo(f"ERROR: {exc}", err=True)
        raise typer.Exit(2) from exc
    s = result["smoke"]
    pkg = loaded.config.package
    if s.get("skipped"):
        typer.echo(f"built {pkg}: smoke skipped; operations: {s['operations']}")
        return
    typer.echo(
        f"built {pkg}: imported {s['imported']} modules, "
        f"{s['failed']} failures; operations: {s['operations']}"
    )
    for name, err in s["failures"][:10]:
        typer.echo(f"  FAIL {name} {err}")
    if s["failed"]:
        raise typer.Exit(1)


@cli_app.command("discover")
def cli_discover(
    product: str = typer.Argument(
        ..., help="product name (products/<name>/) or path to sdk.yml"
    ),
    write_stub: bool = typer.Option(
        False, "--write-stub", help="write products/<name>/cli.yml.stub next to sdk.yml"
    ),
) -> None:
    """print the classification table + cli.yml stub"""
    from .generator.cli.discover import render_stub, render_table

    loaded = _load_or_exit(product)
    ir, _cfg, unmapped = _build_ir_or_exit(loaded)
    typer.echo(render_table(ir, unmapped))
    if write_stub:
        stub_path = Path(loaded.base_dir) / "cli.yml.stub"
        stub_path.write_text(render_stub(ir, unmapped), encoding="utf-8")
        typer.echo(f"\nwrote {stub_path}", err=True)


@cli_app.command("build")
def cli_build(
    product: str = typer.Argument(
        ..., help="product name (products/<name>/) or path to sdk.yml"
    ),
) -> None:
    """emit the CLI project from a built SDK"""
    from . import scaffold
    from .generator.cli.render_cli import cli_overrides_dir, render_cli
    from .generator.cli.scaffold_context import build_cli_scaffold_context

    loaded = _load_or_exit(product)
    ir, cfg, unmapped = _build_ir_or_exit(loaded)
    if loaded.config.project is None and cfg.project is None:
        typer.echo(
            "ERROR: cli build needs project metadata to scaffold the CLI — add a "
            "'project:' block to sdk.yml or cli.yml (see docs/authoring.md)",
            err=True,
        )
        raise typer.Exit(2)
    scaffold_ctx = build_cli_scaffold_context(loaded, ir, cfg)
    cli_pkg = f"{loaded.config.package}_cli"
    out_dir = Path(loaded.output_dir).parent / str(scaffold_ctx["distribution"])
    docs_site_name = (
        f"{scaffold_ctx.get('spec_title')} CLI"
        if scaffold_ctx.get("spec_title")
        else None
    )
    written = render_cli(
        ir,
        package=cli_pkg,
        out_dir=out_dir,
        distribution=str(scaffold_ctx["distribution"]),
        auth=loaded.auth,
        errors=loaded.errors,
        default_headers=getattr(loaded.config, "default_headers", None) or None,
        docs=cfg.docs,
        docs_site_name=docs_site_name,
        docs_repo_url=scaffold_ctx.get("repo_url"),
        docs_description=scaffold_ctx.get("description") or "",
    )
    written = written + scaffold.render_scaffold(
        scaffold.builtin_dir(), cli_overrides_dir(), out_dir, scaffold_ctx
    )
    typer.echo(
        f"emitted {len(written)} files to {out_dir} ({len(ir.commands)} commands)"
    )
    if unmapped:
        typer.echo(
            f"note: {len(unmapped)} unmapped ops omitted (map in cli.yml)", err=True
        )


def main(argv: list[str] | None = None) -> int:
    # VERIFIED against typer 0.26.7 / click 8.4.1 — DO NOT change to catch
    # click.ClickException: standalone_mode=False RETURNS typer.Exit(N)'s code
    # (must capture); typer's exceptions are NOT click.ClickException subclasses;
    # typer.Exit is a RuntimeError. Duck-type on .exit_code/.show().
    # Gives success->0, Exit(2)->2, Exit(1)->1, unknown-cmd->2,
    # missing-arg->2, no-args->2.
    try:
        result = app(args=argv, standalone_mode=False)
        return result if isinstance(result, int) else 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        code = getattr(exc, "exit_code", None)
        if code is not None:
            if hasattr(exc, "show"):
                exc.show()
            return int(code or 0)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
