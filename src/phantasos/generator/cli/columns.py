"""Table-column resolution: model-derived defaults + cli.yml validation.

Columns are JMESPath expressions evaluated (at CLI runtime) against each row
dict produced by model_dump(mode="json") WITHOUT by_alias — i.e. snake_case
Python field names, which is also what build-time validation checks against.
"""

from __future__ import annotations

from typing import Any

import jmespath
from jmespath.exceptions import JMESPathError  # base: covers EmptyExpressionError too

from .cliconfig import ColumnEntry
from .inventory import FieldInfo
from .ir import ColumnSpec

# Identity-ish fields users scan for, in display order.
_PREFERRED = ("id", "name", "type", "status", "state")
_MAX_DEFAULT = 6


def default_columns(fields: list[FieldInfo]) -> list[ColumnSpec]:
    """Preferred names first, then remaining scalar/enum fields in declaration
    order, capped at _MAX_DEFAULT. json-kind (nested) fields are excluded."""
    names = {f.name for f in fields}
    chosen = [n for n in _PREFERRED if n in names]
    for f in fields:
        if len(chosen) >= _MAX_DEFAULT:
            break
        if f.name not in chosen and f.kind in ("scalar", "enum"):
            chosen.append(f.name)
    return [ColumnSpec(header=n, path=n) for n in chosen[:_MAX_DEFAULT]]


def _root_field(node: dict[str, Any]) -> str | None:
    """Leftmost plain field of a parsed JMESPath AST, or None if the root is
    not field-shaped (function, literal, projection of a literal, ...)."""
    while True:
        if node.get("type") == "field":
            return str(node["value"])
        children = node.get("children") or []
        if not children or not isinstance(children[0], dict):
            return None
        node = children[0]


def resolve_columns(entries: list[str | ColumnEntry], fields: list[FieldInfo], obj: str) -> list[ColumnSpec]:
    """Normalize cli.yml column entries; raise ValueError (-> build failure) on
    invalid JMESPath or an unknown root field (best-effort, only when the item
    model's fields are known and the AST root is a plain field)."""
    known = {f.name for f in fields}
    out: list[ColumnSpec] = []
    for e in entries:
        header, path = (e, e) if isinstance(e, str) else (e.header, e.path)
        try:
            parsed = jmespath.compile(path).parsed
        except JMESPathError as exc:
            raise ValueError(f"cli.yml columns.{obj}: invalid JMESPath {path!r}: {exc}") from exc
        root = _root_field(parsed)
        if known and root is not None and root not in known:
            raise ValueError(
                f"cli.yml columns.{obj}: unknown field {root!r} in {path!r} (available: {', '.join(sorted(known))})"
            )
        out.append(ColumnSpec(header=header, path=path))
    return out
