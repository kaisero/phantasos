"""Synthesize illustrative constructor examples from live pydantic models.

Turns an opaque ``Model(...)`` placeholder in the generated CRUD guide into a
real-shaped, type-driven example. Values are honest placeholders: enums use a
real first value; ``str -> "example"``, ``int -> 0``, ``float -> 0.0``,
``bool -> False``, ``datetime -> "2026-01-01T00:00:00Z"``. Domain-perfect
values come from the optional per-product ``docs.examples`` override.
"""

from __future__ import annotations

import datetime
import enum
from types import UnionType
from typing import Union, get_args, get_origin

from pydantic import BaseModel

from ..cli.introspect import _enum_values, _unwrap_optional

_INDENT = "    "
_SCALARS = {
    bool: "False",
    int: "0",
    float: "0.0",
    str: '"example"',
}


def _is_wrapper(model: type[BaseModel]) -> bool:
    return "actual_instance" in getattr(model, "model_fields", {})


def _variants(model: type[BaseModel]) -> list[type[BaseModel]]:
    inner = _unwrap_optional(model.model_fields["actual_instance"].annotation)
    args = get_args(inner) if get_origin(inner) in (Union, UnionType) else ()
    # issubclass(a, BaseModel) already excludes NoneType — an explicit
    # `a is not type(None)` here is redundant and trips mypy's
    # comparison-overlap check under `strict = true`.
    return [a for a in args if isinstance(a, type) and issubclass(a, BaseModel)]


def _pick_variant(
    model: type[BaseModel], variant: str | None
) -> type[BaseModel] | None:
    vs = _variants(model)
    if variant:
        for v in vs:
            if v.__name__ == variant:
                return v
    return vs[0] if vs else None


def _continuation_indent(expr: str, pad: str) -> str:
    """Indent every line of ``expr`` except the first by ``pad``.

    The first line follows ``name=`` and must stay flush; deeper lines align
    under their opening token.
    """
    head, _, tail = expr.partition("\n")
    if not tail:
        return head
    indented = "\n".join(pad + line for line in tail.split("\n"))
    return f"{head}\n{indented}"


def _enum_literal(base: type) -> str:
    values = _enum_values(base) or [""]
    first = values[0]
    if isinstance(base, type) and issubclass(base, enum.Enum):
        members = list(base)
        if members and not isinstance(members[0].value, str):
            return first  # int/other enum -> bare literal
    return f'"{first}"'


def _value(tp: object, seen: frozenset[type]) -> str:
    base = _unwrap_optional(tp)
    if _enum_values(base):
        return _enum_literal(base)  # type: ignore[arg-type]
    origin = get_origin(base)
    if origin in (list, set):
        args = get_args(base)
        item = _value(args[0], seen) if args else '"example"'
        if "\n" in item:
            inner = _continuation_indent(item, _INDENT)
            return f"[\n{_INDENT}{inner},\n]"
        return f"[{item}]"
    if isinstance(base, type) and issubclass(base, BaseModel):
        return _model_expr(base, seen)
    if isinstance(base, type) and issubclass(base, datetime.date):
        return '"2026-01-01T00:00:00Z"'
    if isinstance(base, type):
        for typ, literal in _SCALARS.items():
            if base is typ:
                return literal
    return '"example"'


def _model_expr(model: type[BaseModel], seen: frozenset[type]) -> str:
    if model in seen:
        return f"{model.__name__}(...)"
    seen = seen | {model}
    if _is_wrapper(model):
        variant = _pick_variant(model, None)
        return _model_expr(variant, seen) if variant else f"{model.__name__}(...)"
    lines = [f"{model.__name__}("]
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        value = _continuation_indent(_value(field.annotation, seen), _INDENT)
        lines.append(f"{_INDENT}{name}={value},")
    lines.append(")")
    return "\n".join(lines)


def synthesize_body(model: type[BaseModel], *, variant: str | None = None) -> str:
    """Real-shaped constructor expression for ``model`` (required fields only)."""
    if _is_wrapper(model):
        chosen = _pick_variant(model, variant)
        if chosen is not None:
            return _model_expr(chosen, frozenset({model}))
        return f"{model.__name__}(...)"
    return _model_expr(model, frozenset())
