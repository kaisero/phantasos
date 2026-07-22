"""Render the project scaffold (built-in + per-product overrides) into an SDK."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_BUILTIN = Path(__file__).parent / "scaffold"


def _collect(root: Path | None) -> dict[str, Path]:
    """Map relative-path -> absolute source for every file under root."""
    out: dict[str, Path] = {}
    if root and root.is_dir():
        for p in root.rglob("*"):
            if p.is_file():
                out[str(p.relative_to(root))] = p
    return out


def builtin_dir() -> Path:
    return _BUILTIN


def render_scaffold(builtin: Path, overrides: Path | None, out_dir: Path, context: dict[str, Any]) -> list[str]:
    """Render built-in scaffold + overrides into out_dir. Overrides win by rel-path.

    `.jinja` templates are rendered (suffix stripped); other files are copied
    verbatim. A template that renders to only-whitespace is skipped (used to gate
    optional files like component tests).
    """
    files = _collect(builtin)
    files.update(_collect(overrides))  # overrides win by rel-path key

    # overrides FIRST so same-name templates resolve to the override at render time
    search = [str(p) for p in (overrides, builtin) if p]
    env = Environment(
        loader=FileSystemLoader(search),
        keep_trailing_newline=True,
        autoescape=select_autoescape(),  # renders config/source, not HTML
        undefined=StrictUndefined,
    )
    written: list[str] = []
    for rel, src in sorted(files.items()):
        dest_rel = rel[: -len(".jinja")] if rel.endswith(".jinja") else rel
        dest = out_dir / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if rel.endswith(".jinja"):
            rendered = env.get_template(rel).render(**context)
            if not rendered.strip():
                continue  # gated-out optional file
            dest.write_text(rendered, encoding="utf-8")
        else:
            shutil.copyfile(src, dest)
        written.append(dest_rel)
    return written
