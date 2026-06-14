"""Generate the mechanical sections of .agents/context/ docs.

Each registered block is rendered from the live code (AST) into marker-delimited
regions of a doc, so it cannot rot. ``--check`` regenerates to a buffer and exits
1 if any doc is out of date — the freshness gate runs this. See
docs/specs/2026-06-14-agents-context-docs-design.md.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTEXT = REPO / ".agents" / "context"

# (doc filename, block kind, package dir relative to repo root).
BLOCKS: list[tuple[str, str, str]] = [
    ("sdk-generator.md", "module-map", "src/phantasos/generator/sdk"),
    ("sdk-generator.md", "api", "src/phantasos/generator/sdk"),
]


def _first_doc_line(node: ast.AST) -> str:
    doc = (
        ast.get_docstring(node)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        else None
    )
    return doc.splitlines()[0].strip() if doc else ""


def module_map(pkg_dir: Path) -> str:
    rows = []
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text())
        rows.append(f"- `{path.name}` — {_first_doc_line(tree)}")
    return "\n".join(rows)


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in fn.args.args]
    return f"{fn.name}({', '.join(args)})"


def public_api(pkg_dir: Path) -> str:
    out: list[str] = []
    for path in sorted(pkg_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text())
        items: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                items.append(f"  - class `{node.name}` — {_first_doc_line(node)}")
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                items.append(f"  - `{_signature(node)}` — {_first_doc_line(node)}")
        if items:
            out.append(f"- `{path.name}`")
            out.extend(items)
    return "\n".join(out)


RENDERERS = {"module-map": module_map, "api": public_api}


def render(kind: str, pkg_dir: Path) -> str:
    return RENDERERS[kind](pkg_dir)


def inject(text: str, kind: str, content: str) -> str:
    start, end = f"<!-- GENERATED:{kind} -->", f"<!-- /GENERATED:{kind} -->"
    i, j = text.find(start), text.find(end)
    if i == -1 or j == -1:
        raise ValueError(f"markers for {kind!r} not found")
    return text[: i + len(start)] + "\n" + content + "\n" + text[j:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="fail if any block is stale")
    ns = ap.parse_args(argv)
    stale: list[str] = []
    for doc_name, kind, pkg in BLOCKS:
        doc = CONTEXT / doc_name
        text = doc.read_text()
        updated = inject(text, kind, render(kind, REPO / pkg))
        if ns.check:
            if updated != text:
                stale.append(f"{doc_name}:{kind}")
        else:
            doc.write_text(updated)
    if ns.check and stale:
        print("stale generated blocks: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
