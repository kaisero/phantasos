"""Emit a Typer CLI project from a CliIR (static codegen via Jinja)."""

from __future__ import annotations

import keyword
import re
import shutil
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import ir as _ir_module
from .ir import CliIR, Command, Flag

_TEMPLATES = Path(__file__).parent / "templates"
_HANDOWNED = ["main.py", "hooks.py", "custom/__init__.py"]


def cli_overrides_dir() -> Path:
    return Path(__file__).parent / "cli_overrides"

_RESERVED = {"output", "all_", "dry_run", "verbose", "self"}


def _py_name(param: str) -> str:
    ident = param if param.isidentifier() else "p_" + re.sub(r"\W", "_", param)
    if keyword.iskeyword(ident) or ident in _RESERVED:
        ident += "_"
    return ident


def _leaf(c: Command) -> str | None:
    """The third command segment: a oneOf variant OR a request action (mutually
    exclusive)."""
    return c.variant or c.action


def _func_name(c: Command) -> str:
    base = f"{c.verb}_{c.object}".replace("-", "_")
    leaf = _leaf(c)
    return f"{base}_{leaf}".replace("-", "_") if leaf else base


_SUBVERB_PRIORITY = {
    "patch": 0, "create": 1, "update": 2, "delete": 3,
    "get": 4, "list": 5, "bulk_create": 6, "bulk_delete": 7,
}


def _primary_sub_verb(c: Command) -> str:
    return min(
        (b.sub_verb for b in c.bindings),
        key=lambda s: _SUBVERB_PRIORITY.get(s, 99),
    )


_SCALAR_PY: dict[str, str] = {
    "int": "int", "bool": "bool", "float": "float", "str": "str"
}


def _render_type(f: Flag) -> str:
    base = _SCALAR_PY.get(f.py_type, "str") if f.kind == "scalar" else "str"
    return base if f.required else f"Optional[{base}]"


def _flag_view(f: Flag) -> dict[str, object]:
    choices = f.choices
    help_text: str | None = f.help
    completion: list[str] | None = None
    completer_name: str | None = None
    if choices:
        listed = ", ".join(choices)
        # Escape the leading bracket so rich's markup parser renders it literally
        # (an unescaped "[values: ...]" is treated as a markup tag and dropped).
        values = rf"\[values: {listed}]"
        help_text = f"{f.help}  {values}" if f.help else values
        completion = choices
        completer_name = f"_complete_{_py_name(f.param)}"
    return {
        "name": f.name,
        "param": f.param,
        "py_name": _py_name(f.param),
        "required": f.required,
        "render_type": _render_type(f),
        "help_text": help_text,
        "completion": completion,
        "completer_name": completer_name,
    }


def _command_view(
    c: Command, variant_groups: set[tuple[str, str]]
) -> dict[str, object]:
    leaf = _leaf(c)
    if leaf:
        typer_path: list[str] = [c.object, leaf]
    elif (c.verb, c.object) in variant_groups:
        typer_path = [c.object, _primary_sub_verb(c)]
    else:
        typer_path = [c.object]
    # Deduplicate all_flags: path params take priority; body/query flags whose
    # param name already appears in path_params are suppressed (avoids duplicate
    # argument errors when an SDK body model field shares a name with a path param
    # — e.g. the `type` discriminator that appears both as a path param and as a
    # field of the request body).
    path_param_names = {f.param for f in c.path_params}
    deduped_body = [f for f in c.body_flags if f.param not in path_param_names]
    deduped_query = [
        f for f in c.query_flags
        if f.param not in path_param_names
        and f.param not in {b.param for b in deduped_body}
    ]
    return {
        "key": c.key,
        "func_name": _func_name(c),
        "summary": c.summary,
        "typer_path": typer_path,
        "sdk_resource": c.sdk_resource,
        "verb": c.verb,
        "variant": c.variant,
        "path_params": [_flag_view(f) for f in c.path_params],
        "body_flags": [_flag_view(f) for f in deduped_body],
        "query_flags": [_flag_view(f) for f in deduped_query],
        "all_flags": [
            _flag_view(f)
            for f in (c.path_params + deduped_body + deduped_query)
        ],
    }


def _module_enum_flags(
    cmds: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Deduped enum-flag views (those with a completer) across a module's commands.

    Dedup by ``completer_name`` so a flag shared by several commands in the module
    (e.g. ``--color`` on both create and update) yields a single completer def.
    """
    out: list[dict[str, object]] = []
    seen: set[object] = set()
    for cmd in cmds:
        flags = cast("list[dict[str, object]]", cmd["all_flags"])
        for f in flags:
            name = f.get("completer_name")
            if name and name not in seen:
                seen.add(name)
                out.append(f)
    return out


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
    ctx = {
        "ir": ir,
        "package": package,
        "env_prefix": resolved_prefix,
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
        (c.verb, c.object) for c in ir.commands if c.variant or c.action
    }
    by_resource: dict[str, list[dict[str, object]]] = {r: [] for r in resources}
    for c in ir.commands:
        by_resource[c.sdk_resource].append(_command_view(c, variant_groups))
    for resource, cmds in by_resource.items():
        dest = gen / "commands" / f"{resource}.py"
        # Dedup enum-flag completers by completer_name across the module's commands
        # (e.g. create + update both expose --color → a single completer def).
        module_enum_flags = _module_enum_flags(cmds)
        dest.write_text(
            env.get_template("_generated/commands.py.jinja").render(
                resource=resource, commands=cmds,
                module_enum_flags=module_enum_flags, **ctx),
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

    return written
