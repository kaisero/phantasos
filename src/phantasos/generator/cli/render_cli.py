"""Emit a Typer CLI project from a CliIR (static codegen via Jinja)."""

from __future__ import annotations

import json
import keyword
import re
import shutil
import subprocess
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from . import ir as _ir_module
from .cliconfig import CliDocsConfig
from .docs import build_cli_docs_context
from .flags import dedupe_flags
from .flags import leaf as _leaf
from .flags import query_panel as _query_panel
from .ir import CliIR, Command, Flag

_TEMPLATES = Path(__file__).parent / "templates"
_HANDOWNED = ["main.py", "hooks.py", "custom/__init__.py"]


def cli_overrides_dir() -> Path:
    return Path(__file__).parent / "cli_overrides"


_RESERVED = {
    "output",
    "all_",
    "dry_run",
    "verbose",
    "self",
    "columns",
    "pager",
    "quiet",
}


def _py_name(param: str) -> str:
    ident = param if param.isidentifier() else "p_" + re.sub(r"\W", "_", param)
    if keyword.iskeyword(ident) or ident in _RESERVED:
        ident += "_"
    return ident


def _func_name(c: Command) -> str:
    base = f"{c.verb}_{c.object}".replace("-", "_")
    leaf = _leaf(c)
    return f"{base}_{leaf}".replace("-", "_") if leaf else base


_SUBVERB_PRIORITY = {
    "patch": 0,
    "put": 1,
    "create": 2,
    "update": 3,
    "delete": 4,
    "get": 5,
    "list": 6,
    "bulk_create": 7,
    "bulk_delete": 8,
}


def _primary_sub_verb(c: Command) -> str:
    return min(
        (b.sub_verb for b in c.bindings),
        key=lambda s: _SUBVERB_PRIORITY.get(s, 99),
    )


_SCALAR_PY: dict[str, str] = {
    "int": "int",
    "bool": "bool",
    "float": "float",
    "str": "str",
}


def _py_literal(value: object) -> str:
    """Python source literal for a flag default. json.dumps gives correct
    quoting for str and is wrong for bool/None — handle those explicitly.
    Defaults are documented as scalars; reject anything else loudly rather
    than silently stringifying a YAML list/dict."""
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    raise TypeError(
        f"cli.yml defaults values must be scalars, got {type(value).__name__}"
    )


def _render_type(f: Flag) -> str:
    if f.kind == "scalar" and f.py_type == "bool":
        # Typer maps a ``bool`` annotation to an on/off flag that takes NO value
        # (``--x`` / ``--no-x``). A settable bool field must accept a value like
        # every other flag (``--x true|false``), so render it as a value-taking
        # option (``str``) and coerce it to bool at runtime (see runtime._coerce).
        base = "str"
    elif f.kind == "scalar":
        base = _SCALAR_PY.get(f.py_type, "str")
    else:
        base = "str"
    # ``X | None`` (not ``Optional[X]``) so the emitted source already matches the
    # modern form ``ruff`` (UP rules) would rewrite to — no dangling Optional
    # import to trip F401. Safe pre-3.10 because of ``from __future__ import
    # annotations`` (these are string annotations, never evaluated at runtime).
    return base if f.required else f"{base} | None"


# Max length of a JSON-escaped chunk (the rendered ``"..."`` literal) so that,
# after ``ruff format`` indents it inside ``typer.Option(...)``, the line stays
# <=88. The deepest indent ruff uses for these continuation lines is 12 spaces;
# the single-line ``help="..."`` form carries a ``help=`` prefix (5) at 8-space
# indent. ``88 - 13 = 75`` is the tightest budget; use 74 for a one-char margin.
_HELP_CHUNK_BUDGET = 74


def _help_literal(text: str | None) -> str | None:
    """Python source for a ``help=`` value: a single string literal, or
    implicit-concatenated word-wrapped chunks (so ``ruff format`` can keep each
    line <=88 without truncating the help text).

    Wrapping is measured against the JSON-*escaped* form of each chunk (not the
    raw text) so non-ASCII characters — e.g. an em-dash that serializes to the
    6-char ``\\u2014`` escape — do not inflate a line past the budget.
    """
    if not text:
        return None
    # If the whole thing fits on one escaped line, emit a single literal.
    if len(json.dumps(text)) <= _HELP_CHUNK_BUDGET:
        return json.dumps(text)

    # Greedily pack words into chunks whose escaped form (with a trailing space,
    # except the last) stays within budget.
    words = text.split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}" if current else word
        # measure with the trailing space these non-final chunks will carry
        if current and len(json.dumps(candidate + " ")) > _HELP_CHUNK_BUDGET:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)

    if len(chunks) <= 1:
        return json.dumps(text)
    # trailing space on all but the last so concatenation reproduces the spacing
    parts = [json.dumps(c + " ") for c in chunks[:-1]] + [json.dumps(chunks[-1])]
    return "(" + " ".join(parts) + ")"


def _flag_view(f: Flag, panel: str | None = None) -> dict[str, object]:
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
        "help_literal": _help_literal(help_text),
        "completion": completion,
        "completer_name": completer_name,
        "panel": panel,
        "default_literal": (
            _py_literal(f.cli_default) if f.cli_default is not None else None
        ),
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
    # Dedup flags via the shared helper so the docs command reference can't drift
    # from the emitted flag set (design D2): path wins over body, body over query.
    deduped_body, deduped_query = dedupe_flags(c)
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
            *(_flag_view(f) for f in c.path_params),
            *(_flag_view(f) for f in deduped_body),
            *(_flag_view(f, _query_panel(f)) for f in deduped_query),
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


def _format_generated(paths: list[Path]) -> None:
    """Format the just-written .py files with ruff (idempotent, deterministic).

    Skips silently if ruff is unavailable so the build never hard-fails on it.
    Only the files passed in are touched, so a rebuild never reformats
    hand-owned files this run did not write.
    """
    ruff = shutil.which("ruff")
    pyfiles = [str(p) for p in paths if p.suffix == ".py"]
    if not ruff or not pyfiles:
        return
    common = ["--isolated", "--line-length", "88"]
    # import sorting / safe autofixes first, then format
    subprocess.run(
        [ruff, "check", "--fix", "--select", "I,UP", *common, *pyfiles],
        capture_output=True,
        check=False,
    )
    subprocess.run(
        [ruff, "format", *common, *pyfiles],
        capture_output=True,
        check=False,
    )


def render_cli(
    ir: CliIR,
    package: str,
    out_dir: Path,
    *,
    env_prefix: str | None = None,
    distribution: str | None = None,
    auth: object | None = None,
    errors: object | None = None,
    docs: CliDocsConfig | None = None,
    docs_site_name: str | None = None,
    docs_repo_url: str | None = None,
    docs_description: str = "",
) -> list[str]:
    reserved = sorted({c.object for c in ir.commands if c.object == "cli"})
    if reserved:
        raise ValueError(
            "object name 'cli' is reserved for CLI meta-commands "
            "(show cli history); rename the API object via a cli.yml override"
        )
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
        "distribution": distribution or package,
    }
    # Enrich the IR with credential descriptors from the auth component (if any),
    # BEFORE any template render or the ir.json write, so templates and the
    # serialized IR see the same enriched copy. model_copy returns a new instance,
    # leaving the caller's ir untouched.
    if auth is not None and hasattr(auth, "credential_fields"):
        ir = ir.model_copy(update={"credential_fields": list(auth.credential_fields())})
        ctx["ir"] = ir
    # Likewise enrich the IR with the error-envelope descriptor from the error
    # component, so the emitted diagnostics carries NO product-specific error keys.
    if errors is not None and hasattr(errors, "error_fields"):
        ir = ir.model_copy(update={"error_envelope": errors.error_fields()})
        ctx["ir"] = ir
    written: list[str] = []

    def render(template: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written.append(str(dest.relative_to(out_dir)))

    render("_generated/__init__.py.jinja", gen / "__init__.py")
    render("_generated/config.py.jinja", gen / "config.py")
    render("_generated/default_config.yml.jinja", gen / "default_config.yml")
    render("_generated/config_commands.py.jinja", gen / "config_commands.py")
    render("_generated/history.py.jinja", gen / "history.py")
    render("_generated/cli_commands.py.jinja", gen / "cli_commands.py")
    render("_generated/diagnostics.py.jinja", gen / "diagnostics.py")
    render("_generated/logging_setup.py.jinja", gen / "logging_setup.py")
    render("_generated/output.py.jinja", gen / "output.py")
    render("_generated/runtime.py.jinja", gen / "runtime.py")
    # H1: emit a drift-free typed copy of the IR models so the runtime loads CliIR typed
    spec_src = Path(_ir_module.__file__).read_text(encoding="utf-8")
    (gen / "spec.py").write_text(spec_src, encoding="utf-8")
    written.append(str((gen / "spec.py").relative_to(out_dir)))
    # `config environment` commands — rendered with STATIC per-field typer options
    # generated from ir.credential_fields (no `click` dependency; typer only).
    # Emitted ONLY for auth CLIs; a no-auth CLI never references it (app.py's
    # registration is gated on the same condition).
    if ir.credential_fields:
        render(
            "_generated/environment_commands.py.jinja",
            gen / "environment_commands.py",
        )
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
                resource=resource,
                commands=cmds,
                module_enum_flags=module_enum_flags,
                **ctx,
            ),
            encoding="utf-8",
        )
        written.append(str(dest.relative_to(out_dir)))
    # commands package marker
    (gen / "commands" / "__init__.py").write_text("", encoding="utf-8")
    written.append(str((gen / "commands" / "__init__.py").relative_to(out_dir)))
    # app factory
    all_views = [_command_view(c, variant_groups) for c in ir.commands]
    (gen / "app.py").write_text(
        env.get_template("_generated/app.py.jinja").render(
            resources=resources, commands=all_views, **ctx
        ),
        encoding="utf-8",
    )
    written.append(str((gen / "app.py").relative_to(out_dir)))

    for rel in _HANDOWNED:
        dest = pkg / rel
        if not dest.exists():
            render(f"{rel}.jinja", dest)

    if docs is not None:
        dist = distribution or package
        site_name = docs.site_name or docs_site_name or dist
        doc_ctx = build_cli_docs_context(
            ir,
            docs,
            distribution=dist,
            site_name=site_name,
            repo_url=docs_repo_url,
            description=docs_description,
        )
        merged = {**ctx, **doc_ctx}

        def render_doc(template: str, rel: str, **extra: object) -> None:
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(
                env.get_template(template).render(**merged, **extra), encoding="utf-8"
            )
            written.append(rel)

        render_doc("docs/index.md.jinja", "docs/index.md")
        render_doc("docs/quickstart.md.jinja", "docs/quickstart.md")
        for obj in cast("list[dict[str, object]]", doc_ctx["objects"]):
            render_doc(
                "docs/reference_object.md.jinja",
                f"docs/reference/{obj['object']}.md",
                obj=obj,
            )

    # Format only the files this run wrote (so rebuilds never reformat
    # hand-owned files left untouched above).
    _format_generated([(out_dir / rel) for rel in written if rel.endswith(".py")])

    return written
