"""Import a built SDK and produce a typed OperationInventory."""

from __future__ import annotations

import enum
import importlib
import inspect
import sys
import typing
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

from .inventory import FieldInfo, OperationInfo, OperationInventory, ParamInfo
from .ir import FlagKind

_EXCLUDE_SUFFIXES = ("_with_http_info", "_without_preload_content", "_serialize")
_SKIP_PARAMS = {
    "self",
    "_request_timeout",
    "_request_auth",
    "_content_type",
    "_headers",
    "_host_index",
}


def _public_methods(cls: type[Any]) -> Iterator[tuple[str, object]]:
    for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith("_") or any(name.endswith(s) for s in _EXCLUDE_SUFFIXES):
            continue
        yield name, member


def _enum_values(tp: object) -> list[str] | None:
    if isinstance(tp, type) and issubclass(tp, enum.Enum):
        return [str(m.value) for m in tp]
    if get_origin(tp) is Literal:
        return [str(a) for a in get_args(tp)]
    return None


def _annotated_description(tp: object) -> str:
    """Extract a description from Annotated[..., Field(description=...)] metadata."""
    if get_origin(tp) is not None and hasattr(tp, "__metadata__"):
        for meta in tp.__metadata__:
            desc = getattr(meta, "description", None)
            if desc:
                return str(desc)
    return ""


def _unwrap_optional(tp: object) -> object:
    """Return the underlying type, peeling Annotated[...] and Optional[X]."""
    if get_origin(tp) is not None and hasattr(tp, "__metadata__"):
        tp = get_args(tp)[0]
    if get_origin(tp) in (Union, UnionType):
        non_none = [a for a in get_args(tp) if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap_optional(non_none[0])
    return tp


def _scalar_type(tp: object) -> str:
    """Return the normalized scalar type for path/query/body-field coercion.

    bool must be checked before int because bool is a subclass of int in Python.
    datetime and complex types (UUID, nested model, enum, list, …) map to "str".
    """
    base = _unwrap_optional(tp)
    if base is bool:
        return "bool"
    if base is int:
        return "int"
    if base is float:
        return "float"
    return "str"


def _field_kind(tp: object) -> str:
    tp = _unwrap_optional(tp)
    if _enum_values(tp):
        return "enum"
    if tp in (str, int, float, bool):
        return "scalar"
    origin = get_origin(tp)
    if origin in (list, set):
        inner = _unwrap_optional(get_args(tp)[0]) if get_args(tp) else str
        return "scalar" if inner in (str, int, float, bool) else "json"
    return "json"  # nested model, dict, union, etc.


def _model_fields(model: type[BaseModel]) -> list[FieldInfo]:
    out: list[FieldInfo] = []
    for fname, field in model.model_fields.items():
        tp = field.annotation
        kind = typing.cast(FlagKind, _field_kind(tp))
        # Compute scalar_type only for scalar fields; enums stay "str" (Task 4).
        st = _scalar_type(tp) if kind == "scalar" else "str"
        out.append(
            FieldInfo(
                name=fname,
                annotation=str(tp),
                kind=kind,
                required=field.is_required(),
                default=None if field.is_required() else field.default,
                description=field.description or "",
                enum_values=_enum_values(_unwrap_optional(tp)),
                scalar_type=st,
            )
        )
    return out


def _union_members(model: type[BaseModel]) -> list[str] | None:
    field = model.model_fields.get("actual_instance")
    if field is None:
        return None
    inner = _unwrap_optional(field.annotation)
    if get_origin(inner) in (Union, UnionType):
        return [
            getattr(a, "__name__", None) or str(a)
            for a in get_args(inner)
            if a is not type(None)
        ]
    return None


def _item_fields(item: type[BaseModel]) -> list[FieldInfo]:
    """Fields for a response list item.

    For a oneOf wrapper, return the union (superset) of every variant model's
    fields (dedup by name, first-seen order) instead of the wrapper scaffolding
    (actual_instance / one_of_schemas / ...). This lets default and curated
    columns resolve against the real variant fields.
    """
    members = _union_members(item)
    if not members:
        return _model_fields(item)
    ns: ModuleType = sys.modules[item.__module__]
    seen: set[str] = set()
    out: list[FieldInfo] = []
    for name in members:
        member_cls = getattr(ns, name, None)
        # Skip anything that isn't a real model: a member literally named "List"
        # would resolve to typing.List via getattr (not None), and _model_fields
        # would then crash. Not triggered by today's list-response wrappers, but
        # cheap insurance against a List/Dict-named variant becoming a list item.
        if not (isinstance(member_cls, type) and issubclass(member_cls, BaseModel)):
            continue
        for field in _model_fields(member_cls):
            if field.name in seen:
                continue
            seen.add(field.name)
            out.append(field)
    return out


def _response_info(tp: object) -> tuple[str | None, str | None, list[FieldInfo]]:
    """(return_model, items_field, item_fields) from a return annotation.

    A return model is a list ENVELOPE only when its list[Model] field is named
    "data" or it carries a page_info sibling (every openapi-generator envelope
    we ship matches; a plain item model with an embedded list[Model] — e.g.
    User.user_groups — must NOT be mistaken for one). For an envelope,
    items_field is the list field's name and the fields are the inner model's;
    otherwise the return model itself is the item.
    """
    base = _unwrap_optional(tp)
    if not (isinstance(base, type) and issubclass(base, BaseModel)):
        return None, None, []
    for fname, field in base.model_fields.items():
        inner = _unwrap_optional(field.annotation)
        if get_origin(inner) not in (list, set):
            continue
        if fname != "data" and "page_info" not in base.model_fields:
            continue  # embedded list inside an item model, not an envelope
        args = get_args(inner)
        item = _unwrap_optional(args[0]) if args else None
        if isinstance(item, type) and issubclass(item, BaseModel):
            return base.__name__, fname, _item_fields(item)
    return base.__name__, None, _item_fields(base)


def _docstring_parts(fn: object) -> tuple[str, str]:
    doc = inspect.getdoc(fn) or ""
    if not doc:
        return "", ""
    head, _, rest = doc.partition("\n\n")
    return head.strip(), rest.strip()


def introspect(package: str, sdk_path: Path) -> OperationInventory:
    added = str(sdk_path) not in sys.path
    if added:
        sys.path.insert(0, str(sdk_path))
    try:
        return _introspect(package, sdk_path)
    finally:
        if added and str(sdk_path) in sys.path:
            sys.path.remove(str(sdk_path))


def _introspect(package: str, sdk_path: Path) -> OperationInventory:
    pkg = importlib.import_module(package)
    facade: ModuleType = importlib.import_module(f"{package}.extras.facade")
    resources: dict[str, type[Any]] = facade._RESOURCES

    operations: list[OperationInfo] = []
    for resource, api_cls in resources.items():
        for method, fn in _public_methods(api_cls):
            callable_fn = typing.cast(Callable[..., Any], fn)
            try:
                hints = typing.get_type_hints(callable_fn, include_extras=True)
            except Exception:
                hints = {}
            sig = inspect.signature(callable_fn)
            summary, description = _docstring_parts(callable_fn)
            return_model, items_field, response_fields = _response_info(
                hints.get("return")
            )
            params: list[ParamInfo] = []
            body_fields: dict[str, list[FieldInfo]] = {}
            for pname, p in sig.parameters.items():
                if pname in _SKIP_PARAMS:
                    continue
                tp = hints.get(pname, p.annotation)
                base = _unwrap_optional(tp)
                required = p.default is inspect.Parameter.empty
                # TODO(phase2): detect dict and list[Model] request bodies (currently
                # classified as path/query because they are not BaseModel subclasses).
                is_body = isinstance(base, type) and issubclass(base, BaseModel)
                if is_body:
                    location: str = "body"
                elif required:
                    location = "path"
                else:
                    location = "query"
                info = ParamInfo(
                    name=pname,
                    annotation=str(tp),
                    location=location,  # type: ignore[arg-type]
                    required=required,
                    default=None if required else p.default,
                    description=_annotated_description(tp),
                    enum_values=_enum_values(base),
                    scalar_type=_scalar_type(tp),
                )
                if is_body and isinstance(base, type) and issubclass(base, BaseModel):
                    info.body_model = base.__name__
                    members = _union_members(base)
                    info.union_members = members
                    if members:
                        ns: ModuleType = sys.modules[base.__module__]
                        for m in members:
                            member_cls = getattr(ns, m, None)
                            if member_cls is None:
                                # member not importable from wrapper module; skip
                                continue
                            body_fields[m] = _model_fields(member_cls)
                    else:
                        body_fields[base.__name__] = _model_fields(base)
                params.append(info)
            operations.append(
                OperationInfo(
                    resource=resource,
                    method=method,
                    summary=summary,
                    description=description,
                    params=params,
                    body_fields=body_fields,
                    return_model=return_model,
                    items_field=items_field,
                    response_fields=response_fields,
                )
            )
    return OperationInventory(
        sdk_package=package,
        sdk_version=getattr(pkg, "__version__", "0.0.0"),
        operations=operations,
    )
