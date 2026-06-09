"""Emit a Typer CLI project from a CliIR (static codegen via Jinja)."""

from __future__ import annotations

import keyword
import re
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import ir as _ir_module
from .ir import CliIR, Command, Flag

_TEMPLATES = Path(__file__).parent / "templates"
_HANDOWNED = ["main.py", "hooks.py", "custom/__init__.py"]

_RESERVED = {"output", "all_", "dry_run", "verbose", "replace", "self"}


def _py_name(param: str) -> str:
    ident = param if param.isidentifier() else "p_" + re.sub(r"\W", "_", param)
    if keyword.iskeyword(ident) or ident in _RESERVED:
        ident += "_"
    return ident


def _func_name(c: Command) -> str:
    base = f"{c.verb}_{c.object}".replace("-", "_")
    return (f"{base}_{c.variant}".replace("-", "_")) if c.variant else base


_SUBVERB_PRIORITY = {
    "patch": 0, "create": 1, "update": 2, "delete": 3,
    "get": 4, "list": 5, "bulk_create": 6, "bulk_delete": 7,
}


def _primary_sub_verb(c: Command) -> str:
    return min(
        (b.sub_verb for b in c.bindings),
        key=lambda s: _SUBVERB_PRIORITY.get(s, 99),
    )


def _flag_view(f: Flag) -> dict[str, str]:
    return {
        "name": f.name, "param": f.param,
        "py_name": _py_name(f.param), "help": f.help,
    }


def _command_view(
    c: Command, variant_groups: set[tuple[str, str]]
) -> dict[str, object]:
    if c.variant:
        typer_path: list[str] = [c.object, c.variant]
    elif (c.verb, c.object) in variant_groups:
        typer_path = [c.object, _primary_sub_verb(c)]
    else:
        typer_path = [c.object]
    return {
        "key": c.key,
        "func_name": _func_name(c),
        "summary": c.summary,
        "typer_path": typer_path,
        "sdk_resource": c.sdk_resource,
        "verb": c.verb,
        "variant": c.variant,
        "path_params": [_flag_view(f) for f in c.path_params],
        "body_flags": [_flag_view(f) for f in c.body_flags],
        "query_flags": [_flag_view(f) for f in c.query_flags],
        "all_flags": [
            _flag_view(f) for f in (c.path_params + c.body_flags + c.query_flags)
        ],
    }


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES)),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),  # renders Python source, not HTML
        undefined=StrictUndefined,
    )


def render_cli(
    ir: CliIR,
    package: str,
    out_dir: Path,
    *,
    env_prefix: str | None = None,
    distribution: str | None = None,
    sdk_dependency: str | None = None,
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
    resolved_distribution = distribution or package.replace("_", "-")
    resolved_sdk_dependency = sdk_dependency or ir.sdk_package
    ctx = {
        "ir": ir,
        "package": package,
        "env_prefix": resolved_prefix,
        "distribution": resolved_distribution,
        "sdk_dependency": resolved_sdk_dependency,
    }
    written: list[str] = []

    def render(template: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written.append(str(dest.relative_to(out_dir)))

    render("_generated/__init__.py.jinja", gen / "__init__.py")
    render("_generated/config.py.jinja", gen / "config.py")
    render("_generated/output.py.jinja", gen / "output.py")
    render("_generated/runtime.py.jinja", gen / "runtime.py")
    # H1: emit a drift-free typed copy of the IR models so the runtime loads CliIR typed
    spec_src = Path(_ir_module.__file__).read_text(encoding="utf-8")
    (gen / "spec.py").write_text(spec_src, encoding="utf-8")
    written.append(str((gen / "spec.py").relative_to(out_dir)))
    (gen / "ir.json").write_text(ir.model_dump_json(indent=2), encoding="utf-8")
    written.append(str((gen / "ir.json").relative_to(out_dir)))

    # Emit per-resource command modules
    resources = sorted({c.sdk_resource for c in ir.commands})
    variant_groups: set[tuple[str, str]] = {
        (c.verb, c.object) for c in ir.commands if c.variant
    }
    by_resource: dict[str, list[dict[str, object]]] = {r: [] for r in resources}
    for c in ir.commands:
        by_resource[c.sdk_resource].append(_command_view(c, variant_groups))
    for resource, cmds in by_resource.items():
        dest = gen / "commands" / f"{resource}.py"
        dest.write_text(
            env.get_template("_generated/commands.py.jinja").render(
                resource=resource, commands=cmds, **ctx),
            encoding="utf-8")
        written.append(str(dest.relative_to(out_dir)))
    # commands package marker
    (gen / "commands" / "__init__.py").write_text("", encoding="utf-8")
    written.append(str((gen / "commands" / "__init__.py").relative_to(out_dir)))
    # app factory
    all_views = [_command_view(c, variant_groups) for c in ir.commands]
    (gen / "app.py").write_text(
        env.get_template("_generated/app.py.jinja").render(
            resources=resources, commands=all_views, **ctx),
        encoding="utf-8")
    written.append(str((gen / "app.py").relative_to(out_dir)))

    for rel in _HANDOWNED:
        dest = pkg / rel
        if not dest.exists():
            render(f"{rel}.jinja", dest)

    pyproject = out_dir / "pyproject.toml"
    if not pyproject.exists():
        pyproject.write_text(
            env.get_template("pyproject.toml.jinja").render(**ctx), encoding="utf-8"
        )
        written.append("pyproject.toml")

    return written
