"""Vendor step: render selected component templates into the SDK's extras/."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .productconfig import LoadedProduct

if TYPE_CHECKING:
    from jinja2 import Environment

_COMPONENTS_DIR = Path(__file__).parent / "components"
_IMPORT_RE = re.compile(r"^from \S+\.api\.(\w+) import (\w+)\s*$", re.M)


def _env() -> Environment:
    from jinja2 import Environment, FileSystemLoader

    # autoescape stays off: templates render Python source, not HTML — HTML escaping
    # would corrupt the generated code (e.g. `>` -> `&gt;`).
    return Environment(
        loader=FileSystemLoader(str(_COMPONENTS_DIR)),
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701  renders Python source, not HTML
    )


def _discover_resources(pkg_dir: Path) -> list[dict[str, str]]:
    """[{attr, module, cls}] from the generated api/__init__.py import lines."""
    init = (pkg_dir / "api" / "__init__.py").read_text(encoding="utf-8")
    out: list[dict[str, str]] = []
    for module, cls in _IMPORT_RE.findall(init):
        out.append(
            {
                "module": module,
                "cls": cls,
                "attr": module[:-4] if module.endswith("_api") else module,
            }
        )
    return out


def vendor(pkg_dir: Path, loaded: LoadedProduct) -> list[str]:
    from jinja2 import Environment, FileSystemLoader

    extras = pkg_dir / "extras"
    extras.mkdir(exist_ok=True)
    written: list[str] = []
    ctx = dict(loaded.context)

    builtin_env = _env()
    product_env = Environment(
        loader=FileSystemLoader(str(loaded.base_dir)),
        keep_trailing_newline=True,
        autoescape=False,  # noqa: S701  renders Python source, not HTML
    )

    def render_template(template: str, **extra: Any) -> str:
        merged = {**ctx, **extra}
        if Path(template).is_absolute():
            rel = Path(template).relative_to(loaded.base_dir)
            return product_env.get_template(str(rel)).render(**merged)
        return builtin_env.get_template(template).render(**merged)

    def write_component(name: str, component: Any, **extra: Any) -> None:
        fields = component.model_dump()
        template = fields.pop("template")
        fields.pop("type", None)
        (extras / name).write_text(
            render_template(template, **{**fields, **extra}), encoding="utf-8"
        )
        written.append(name)

    if loaded.auth:
        write_component("auth.py", loaded.auth)
    if loaded.pagination:
        write_component("pagination.py", loaded.pagination)
    if loaded.errors:
        write_component("errors.py", loaded.errors)
    if loaded.facade:
        write_component(
            "facade.py", loaded.facade, resources=_discover_resources(pkg_dir)
        )

    for dest, source in loaded.config.include.items():
        target = (extras / dest).resolve()
        if not target.is_relative_to(extras.resolve()):
            raise ValueError(f"include destination {dest!r} escapes extras/")
        target.parent.mkdir(parents=True, exist_ok=True)
        rel = (loaded.base_dir / source).resolve().relative_to(loaded.base_dir)
        target.write_text(
            product_env.get_template(str(rel)).render(**ctx), encoding="utf-8"
        )
        written.append(dest)

    (extras / "__init__.py").write_text(
        builtin_env.get_template("extras_init.py.jinja").render(**ctx), encoding="utf-8"
    )
    written.append("__init__.py")
    return written
