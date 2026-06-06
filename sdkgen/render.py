"""Vendor step: render selected component templates into the SDK's extras/."""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path

_COMPONENTS_DIR = Path(__file__).parent / "components"
_IMPORT_RE = re.compile(r"^from \S+\.api\.(\w+) import (\w+)\s*$", re.M)


def _env():
    from jinja2 import Environment, FileSystemLoader
    return Environment(loader=FileSystemLoader(str(_COMPONENTS_DIR)), keep_trailing_newline=True)


def _discover_resources(pkg_dir: Path):
    """[{attr, module, cls}] from the generated api/__init__.py import lines."""
    init = (pkg_dir / "api" / "__init__.py").read_text(encoding="utf-8")
    out = []
    for module, cls in _IMPORT_RE.findall(init):
        out.append({"module": module, "cls": cls, "attr": module[:-4] if module.endswith("_api") else module})
    return out


def vendor(pkg_dir: Path, config) -> list[str]:
    env = _env()
    extras = pkg_dir / "extras"
    extras.mkdir(exist_ok=True)
    written = []

    flags = {
        "has_auth": config.auth is not None,
        "has_pagination": config.pagination is not None,
        "has_errors": config.errors is not None,
        "has_facade": config.facade is not None,
        "config_class_name": config.auth.config_class_name if config.auth else "SdkConfiguration",
    }

    def write(name, component, **extra):
        ctx = asdict(component)
        template = ctx.pop("template")
        ctx.update(extra)
        (extras / name).write_text(env.get_template(template).render(**ctx), encoding="utf-8")
        written.append(name)

    if config.auth:
        write("auth.py", config.auth, base_url=config.base_url)
    if config.pagination:
        write("pagination.py", config.pagination)
    if config.errors:
        write("errors.py", config.errors)
    if config.facade:
        write("facade.py", config.facade, resources=_discover_resources(pkg_dir),
              has_auth=flags["has_auth"], has_pagination=flags["has_pagination"])
    (extras / "__init__.py").write_text(
        env.get_template("extras_init.py.jinja").render(**flags), encoding="utf-8")
    written.append("__init__.py")
    return written
