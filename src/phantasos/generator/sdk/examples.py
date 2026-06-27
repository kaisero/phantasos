"""Synthesize illustrative constructor examples from live pydantic models.

Turns an opaque ``Model(...)`` placeholder in the generated CRUD guide into a
real-shaped, type-driven example. Values are honest placeholders: enums use a
real first value; ``str -> "example"``, ``int -> 0``, ``float -> 0.0``,
``bool -> False``, ``datetime -> "2026-01-01T00:00:00Z"``. Domain-perfect
values come from the optional per-product ``docs.examples`` override.

Placeholders must also CONSTRUCT the model: a bare Mapping field (``dict`` /
``object`` / ``Any``) gets ``{}`` (not ``"example"``); a constrained int gets
the smallest value its ``ge``/``gt``/``le``/``lt`` metadata allows; and a
required field that can't be filled validly (an unresolved forward-ref) drops
its whole level to the honest opaque ``Name(...)`` rather than emit a
runnable-looking-but-invalid example.
"""

from __future__ import annotations

import datetime
import enum
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from ..opmodel.introspect import _enum_values, _unwrap_optional

_INDENT = "    "
_SCALARS = {
    bool: "False",
    int: "0",
    float: "0.0",
    str: '"example"',
}


# OAG anyOf/oneOf wrappers carry one `<any|one>of_schema_N_validator` field per
# branch — the reliable variant signal. `actual_instance` is unreliable: anyOf
# emits it as `Any` at runtime (the Union is TYPE_CHECKING-only), so resolve
# variants from the validator fields. (Local copy by design — generator/sdk and
# the docs gen-script duplicate this resolver rather than share it.)
_VALIDATOR = re.compile(r"(any|one)of_schema_\d+_validator$")
# A SCM container branch is a wrapper whose every leaf is a single placement
# field — collapsed in examples so the body shows a real PAYLOAD, not `folder=`.
_CONTAINER_FIELDS = {"folder", "snippet", "device"}


def _is_wrapper(model: type[BaseModel]) -> bool:
    return any(_VALIDATOR.match(f) for f in getattr(model, "model_fields", {}))


def _variants(model: type[BaseModel]) -> list[type[BaseModel]]:
    out: list[type[BaseModel]] = []
    for name, field in model.model_fields.items():
        if not _VALIDATOR.match(name):
            continue
        a = _unwrap_optional(field.annotation)  # `Optional[Variant]` -> Variant
        if isinstance(a, type) and issubclass(a, BaseModel):
            out.append(a)
    return list(dict.fromkeys(out))  # de-dupe, preserve order


def _is_container(model: type[BaseModel]) -> bool:
    """True iff every branch is a leaf with a single placement field.

    Keys only on the ``{folder,snippet,device}`` leaf signature (generic; no
    spec identifiers), so the SCM container branch is skipped as a body example.
    """
    if not _is_wrapper(model):
        return False
    for leaf in _variants(model):
        if _is_wrapper(leaf):
            return False
        real = [f for f in leaf.model_fields if f != "additional_properties"]
        if not (len(real) == 1 and real[0] in _CONTAINER_FIELDS):
            return False
    return True


def _pick_variant(
    model: type[BaseModel], variant: str | None
) -> type[BaseModel] | None:
    vs = [v for v in _variants(model) if not _is_container(v)]  # skip container
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
    return json.dumps(first)


def _int_literal(meta: Iterable[Any]) -> str:
    """Smallest int satisfying any ``ge``/``gt``/``le``/``lt`` constraint (else 0).

    Reads pydantic ``FieldInfo.metadata`` (annotated-types ``Ge``/``Gt``/… each
    expose the matching attribute) so a constrained int yields a value the model
    ACCEPTS — ``ge=1 -> 1``, ``gt=0 -> 1`` — instead of an out-of-bounds ``0``.
    """
    lo: int | None = None
    hi: int | None = None
    for m in meta:
        ge, gt = getattr(m, "ge", None), getattr(m, "gt", None)
        le, lt = getattr(m, "le", None), getattr(m, "lt", None)
        if ge is not None:
            lo = ge if lo is None else max(lo, ge)
        if gt is not None:
            lo = gt + 1 if lo is None else max(lo, gt + 1)
        if le is not None:
            hi = le if hi is None else min(hi, le)
        if lt is not None:
            hi = lt - 1 if hi is None else min(hi, lt - 1)
    value = 0
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return str(value)


def _is_mapping(base: object) -> bool:
    """True for a bare Mapping field: ``dict`` / ``object`` / ``Any`` / Mapping.

    Such a field has no declared properties, so the model wants ``{}`` — a string
    ``"example"`` is rejected with a ``dict_type`` ValidationError.
    """
    if base is dict or base is object or base is Any:
        return True
    if get_origin(base) is dict:
        return True
    return isinstance(base, type) and issubclass(base, Mapping)


def _value(tp: object, seen: frozenset[type], meta: Iterable[Any] = ()) -> str | None:
    """Synthesized value for a field; ``None`` means it can't be filled validly."""
    base = _unwrap_optional(tp)
    if _enum_values(base):
        return _enum_literal(base)  # type: ignore[arg-type]
    origin = get_origin(base)
    if origin in (list, set):
        args = get_args(base)
        item = _value(args[0], seen) if args else '"example"'
        if item is None:
            return None  # unfillable item -> drop the level upstream
        if "\n" in item:
            inner = _continuation_indent(item, _INDENT)
            return f"[\n{_INDENT}{inner},\n]"
        return f"[{item}]"
    if isinstance(base, type) and issubclass(base, BaseModel):
        return _model_expr(base, seen)
    if isinstance(base, type) and issubclass(base, datetime.date):
        return '"2026-01-01T00:00:00Z"'
    if base is int:  # before the scalar table so constraints are honoured
        return _int_literal(meta)
    if isinstance(base, type):
        for typ, literal in _SCALARS.items():
            if base is typ:
                return literal
    if _is_mapping(base):
        return "{}"
    if isinstance(base, type):
        return '"example"'  # an unrecognised concrete type (UUID, IP, ...)
    return None  # ForwardRef / unresolved annotation: caller makes the level opaque


def _model_expr(
    model: type[BaseModel], seen: frozenset[type], *, variant: str | None = None
) -> str:
    if model in seen:
        return f"{model.__name__}(...)"
    seen = seen | {model}
    if _is_wrapper(model):
        # WRAP the child as one positional arg: the SDK accepts only the fully
        # nested form `Wrapper(SubWrapper(Leaf(...)))` (the bare leaf raises
        # ValidationError). A payload sub-wrapper descends to its leaf here.
        chosen = _pick_variant(model, variant)
        if chosen is None:
            return f"{model.__name__}(...)"
        inner = _continuation_indent(_model_expr(chosen, seen), _INDENT)
        return f"{model.__name__}({inner})"
    lines = [f"{model.__name__}("]
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        rendered = _value(field.annotation, seen, field.metadata)
        if rendered is None:
            # A required field can't be filled validly: an honest opaque level
            # beats a runnable-looking example that raises ValidationError (D3).
            return f"{model.__name__}(...)"
        value = _continuation_indent(rendered, _INDENT)
        lines.append(f"{_INDENT}{name}={value},")
    lines.append(")")
    return "\n".join(lines)


def synthesize_body(model: type[BaseModel], *, variant: str | None = None) -> str:
    """Real-shaped constructor expression for ``model`` (required fields only).

    A wrapper body is emitted FULLY nested — ``Wrapper(SubWrapper(Leaf(...)))`` —
    because the SDK rejects the unwrapped leaf; ``variant`` selects the top-level
    branch (a container branch is skipped in favour of a real payload).
    """
    return _model_expr(model, frozenset(), variant=variant)


# ---------------------------------------------------------------------------
# Tier 1: reference_example + assemble_reference_docstring
# ---------------------------------------------------------------------------

# `Name()` / `Name(\n)` — an empty constructor: a plain all-optional PATCH body.
# These are NOT suppressed; they render as `body=Name()  # all fields optional`.
# A discriminated PATCH renders `Name(\n    type="x",\n)` (non-empty) and is not
# matched — it shows its body verbatim.
_EMPTY_CTOR = re.compile(r"^\w+\(\s*\)\Z")
_DOC_INDENT = " " * 8  # method-body docstring indentation


def _example_block(code: str) -> str:
    """Wrap a code snippet as the Markdown example block griffe renders."""
    return f"**Example:**\n\n```python\n{code}\n```"


def reference_example(
    *,
    attr: str,
    method: str,
    path_args: list[tuple[str, str]],
    body_model: type[BaseModel] | None,
    variant: str | None = None,
    override: str | None = None,
) -> str | None:
    """The `**Example:**` block for one wrapper op (always returns a block here).

    - `override` (showcase only) is used verbatim — author-written, not
      synthesized — so it wins even for an all-optional body (D6).
    - An empty synthesized body (a plain all-optional PATCH) is NOT suppressed:
      it renders as `body=Name()  # all fields optional` so the client path +
      model are visible and the user fills the fields (D2).
    - The call always shows the client navigation path `client.<attr>.<method>`
      plus required path args; the body kwarg is appended when present (D3).

    (`None` is reserved for future "truly nothing to show" cases; with current
    policy every op yields a block.)
    """
    if override is not None:
        return _example_block(override.strip())
    body_code: str | None = None
    body_comment = ""
    if body_model is not None:
        synthesized = synthesize_body(body_model, variant=variant)
        if _EMPTY_CTOR.match(synthesized):
            # All-optional body: show the actually-constructed type (the model, or
            # a chosen oneOf variant) as an empty, valid call + an optionality hint.
            ctor = synthesized.split("(", 1)[0]
            body_code = f"{ctor}()"
            body_comment = "  # all fields optional"
        else:
            body_code = synthesized
    lines = [f"client.{attr}.{method}("]
    for name, placeholder in path_args:
        lines.append(f'    {name}="{placeholder}",')
    if body_code is not None:
        body_expr = _continuation_indent(body_code, _INDENT)
        lines.append(f"    body={body_expr},{body_comment}")
    code = f"client.{attr}.{method}()" if len(lines) == 1 else "\n".join(lines) + "\n)"
    return _example_block(code)


def assemble_reference_docstring(summary: str, example: str | None) -> str:
    """Combine the one-line summary with an example block into a docstring body.

    The summary stays flush (it follows the opening triple-quote); every
    non-blank continuation line is indented to the method-body level so the
    emitted ``\"\"\"{{ m.docstring }}\"\"\"`` is valid Python. griffe's docstring
    cleaner dedents it before rendering.
    """
    if example is None:
        return summary
    body = f"{summary}\n\n{example}"
    head, _, tail = body.partition("\n")
    cont = "\n".join(_DOC_INDENT + ln if ln else "" for ln in tail.split("\n"))
    return f"{head}\n{cont}"
