"""Federated runtime-hoist pass (libcst).

After the federated build loop, each ``<root>/<slug>/`` carries its OWN copy of the
five OAG runtime modules (``api_client``, ``configuration``, ``rest``, ``exceptions``,
``api_response``) — N near-identical copies. :func:`hoist_runtime` collapses them into
one shared ``<root>/_runtime/`` and repoints every import that targets a runtime module
to absolute ``<root>._runtime.X``.

Why libcst, not regex (B1): ``ApiClient.__init__`` is a real multi-line
``def __init__(self, configuration=None, ...) -> None:`` a regex can't match safely.
The pass never touches ``__init__``; instead it adds a class-level ``models = None``
default and rewrites the one package-bound line
``getattr(<root>.<donor>.models, klass)`` -> ``getattr(self.models, klass)``. The
composer (P2.1) sets ``.models`` per handle.

The import rewriter resolves each ``ImportFrom`` against the current file's package so
it handles all three real OAG shapes: dotted ``from <root>.<slug>.rest import …`` (and
``<root>.<slug>.X``), non-dotted ``from <root>.<slug> import rest`` (B2), and relative
``from ..exceptions import …`` in ``extras/`` (B3). Model imports (``….models.*``) and
the facade are left untouched.

The per-slug walk covers the WHOLE sub-tree (not just ``api/`` + ``extras/``): the
sub-package ``__init__.py`` re-exports the runtime symbols too (real OAG:
``from <root>.<slug>.api_client import ApiClient as ApiClient``), and importing anything
under ``<slug>`` executes it. ``models/`` never imports runtime, so it is skipped.
"""

from __future__ import annotations

from pathlib import Path

import libcst as cst

_RUNTIME = frozenset(
    {"api_client", "configuration", "rest", "exceptions", "api_response"}
)
_FILES = tuple(f"{m}.py" for m in _RUNTIME)


def _dotted(node: cst.BaseExpression | None) -> str | None:
    """Flatten a ``Name``/``Attribute`` dotted-name chain to a string."""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr.value}" if base else node.attr.value
    return None


def _names_hit_runtime(importfrom: cst.ImportFrom) -> bool:
    """True if any imported *name* in ``from X import …`` is a runtime module (B2)."""
    names = importfrom.names
    if isinstance(names, cst.ImportStar):
        return False
    return any(alias.name.value in _RUNTIME for alias in names)


def _is_docstring(stmt: cst.BaseStatement) -> bool:
    return (
        isinstance(stmt, cst.SimpleStatementLine)
        and len(stmt.body) == 1
        and isinstance(stmt.body[0], cst.Expr)
        and isinstance(stmt.body[0].value, cst.SimpleString | cst.ConcatenatedString)
    )


class _Rewrite(cst.CSTTransformer):
    """Repoint runtime-targeting imports to absolute ``<root>._runtime.X``."""

    def __init__(self, root: str, current_pkg: str) -> None:
        self.root = root
        self.cur = current_pkg
        tail = current_pkg[len(root) + 1 :]
        # sub-package = root + first segment beyond it (``prisma_access.objects``).
        self.sub_pkg = f"{root}.{tail.split('.')[0]}" if tail else root

    def _abs(self, level: int, module: str | None) -> str | None:
        """Resolve a (possibly relative) import to an absolute dotted module."""
        if level == 0:
            return module
        parts = self.cur.split(".")
        # ``from .`` (level 1) = current package; each extra dot drops one segment.
        keep = len(parts) - (level - 1)
        base = parts[:keep] if keep > 0 else []
        joined = [*base, module] if module else base
        return ".".join(joined) if joined else None

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.BaseSmallStatement:
        mod = self._abs(len(updated_node.relative), _dotted(updated_node.module))
        if mod is None:
            return updated_node
        tail = mod.rsplit(".", 1)[-1]
        # Only a DIRECT child of the sub-package is a runtime module: a schema named
        # `Configuration`/`ApiResponse`/etc. lands at `<sub_pkg>.models.configuration`,
        # whose tail is also runtime-named — the `mod == <sub_pkg>.<tail>` guard keeps
        # that model import untouched instead of mis-hoisting it to `_runtime`.
        if tail in _RUNTIME and mod == f"{self.sub_pkg}.{tail}":  # dotted / relative B3
            return updated_node.with_changes(
                relative=[],
                module=cst.parse_expression(f"{self.root}._runtime.{tail}"),
            )
        # B2: ``from <pkg> import rest`` (the imported name is a runtime module).
        if mod == self.sub_pkg and _names_hit_runtime(updated_node):
            return updated_node.with_changes(
                relative=[],
                module=cst.parse_expression(f"{self.root}._runtime"),
            )
        return updated_node


class _AbstractModels(cst.CSTTransformer):
    """B1: make ``ApiClient`` package-agnostic without touching ``__init__``.

    (a) drop ``import <root>.<donor>.models``; (b) ``getattr(<that>, klass)`` ->
    ``getattr(self.models, klass)``; (c) insert a class-level ``models = None`` default.
    """

    def __init__(self, root: str, donor: str) -> None:
        self.target = f"{root}.{donor}.models"

    def visit_Import(self, node: cst.Import) -> bool:
        # Don't descend into ``import a.b.models`` — its dotted name must NOT be caught
        # by ``leave_Attribute`` (the whole statement is dropped below instead).
        return False

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.BaseStatement | cst.RemovalSentinel:
        kept = [
            s
            for s in updated_node.body
            if not (
                isinstance(s, cst.Import)
                and any(_dotted(a.name) == self.target for a in s.names)
            )
        ]
        if not kept:
            return cst.RemoveFromParent()
        if len(kept) != len(updated_node.body):
            return updated_node.with_changes(body=kept)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        if _dotted(updated_node) == self.target:
            return cst.Attribute(value=cst.Name("self"), attr=cst.Name("models"))
        return updated_node

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.BaseStatement:
        if updated_node.name.value != "ApiClient" or not isinstance(
            updated_node.body, cst.IndentedBlock
        ):
            return updated_node
        stmts = list(updated_node.body.body)
        idx = 1 if stmts and _is_docstring(stmts[0]) else 0  # keep the docstring first
        stmts.insert(idx, cst.parse_statement("models = None\n"))
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=tuple(stmts))
        )


def _rewrite_file(path: Path, root: str, current_pkg: str) -> None:
    tree = cst.parse_module(path.read_text(encoding="utf-8"))
    path.write_text(tree.visit(_Rewrite(root, current_pkg)).code, encoding="utf-8")


def _abstract_models(path: Path, root: str, donor: str) -> None:
    tree = cst.parse_module(path.read_text(encoding="utf-8"))
    path.write_text(tree.visit(_AbstractModels(root, donor)).code, encoding="utf-8")


def hoist_runtime(project_dir: Path, root_package: str, slugs: list[str]) -> None:
    """Collapse the per-sub OAG runtime into one shared ``<root>/_runtime/``.

    *project_dir* is the distribution root (the dir on ``sys.path``); *root_package*
    is the (possibly dotted) parent package (``prisma_access``); *slugs* are the
    sub-package leaf names. The first slug is the donor whose runtime copy is hoisted.
    """
    root = project_dir / Path(*root_package.split("."))
    rt = root / "_runtime"
    rt.mkdir(parents=True, exist_ok=True)
    (rt / "__init__.py").write_text("", encoding="utf-8")

    donor = slugs[0]
    donor_pkg = f"{root_package}.{donor}"
    # 1. Hoist the donor's runtime files and repoint their own runtime imports.
    for fname in _FILES:
        (rt / fname).write_text(
            (root / donor / fname).read_text(encoding="utf-8"), encoding="utf-8"
        )
        _rewrite_file(rt / fname, root_package, donor_pkg)
    _abstract_models(rt / "api_client.py", root_package, donor)

    # 2. Delete every per-sub runtime copy.
    for slug in slugs:
        for fname in _FILES:
            (root / slug / fname).unlink(missing_ok=True)

    # 3. Repoint every remaining runtime-targeting import under each sub-package
    #    (whole sub-tree incl. <slug>/__init__.py; models/ never imports runtime).
    for slug in slugs:
        sub = root / slug
        for f in sub.rglob("*.py"):
            if "models" in f.relative_to(sub).parts:
                continue
            current_pkg = ".".join([root_package, *f.parent.relative_to(root).parts])
            _rewrite_file(f, root_package, current_pkg)
