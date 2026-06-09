"""Emit a Typer CLI project from a CliIR (static codegen via Jinja)."""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import ir as _ir_module
from .ir import CliIR

_TEMPLATES = Path(__file__).parent / "templates"
_HANDOWNED = ["main.py", "hooks.py", "custom/__init__.py"]


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),  # renders Python source, not HTML
        undefined=StrictUndefined,
    )


def render_cli(
    ir: CliIR, package: str, out_dir: Path, *, env_prefix: str | None = None
) -> list[str]:
    env = _env()
    pkg = out_dir / package
    gen = pkg / "_generated"
    if gen.exists():
        if not gen.resolve().is_relative_to(pkg.resolve()):
            raise ValueError("refusing to wipe a path outside the package")
        shutil.rmtree(gen)
    (gen / "commands").mkdir(parents=True, exist_ok=True)
    resolved_prefix = env_prefix or package.upper().removesuffix("_CLI")
    ctx = {"ir": ir, "package": package, "env_prefix": resolved_prefix}
    written: list[str] = []

    def render(template: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written.append(str(dest.relative_to(out_dir)))

    render("_generated/__init__.py.jinja", gen / "__init__.py")
    render("_generated/config.py.jinja", gen / "config.py")
    # H1: emit a drift-free typed copy of the IR models so the runtime loads CliIR typed
    spec_src = Path(_ir_module.__file__).read_text(encoding="utf-8")
    (gen / "spec.py").write_text(spec_src, encoding="utf-8")
    written.append(str((gen / "spec.py").relative_to(out_dir)))
    (gen / "ir.json").write_text(ir.model_dump_json(indent=2), encoding="utf-8")
    written.append(str((gen / "ir.json").relative_to(out_dir)))

    for rel in _HANDOWNED:
        dest = pkg / rel
        if not dest.exists():
            render(f"{rel}.jinja", dest)
    return written
