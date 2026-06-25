"""Walk live SDK body models into the deduped CliIR model registry.

CLI-owned (separation-of-duty): reuses the opmodel walking primitives but emits
the CLI's own ModelField/ModelSchema descriptors. The recursion lives here, not
in opmodel, so the shared FieldInfo/OperationInfo stay untouched (spec D8).
"""

from __future__ import annotations

import importlib
import sys
import typing
from pathlib import Path
from types import UnionType

from pydantic import BaseModel

from ..opmodel.introspect import (
    enum_values,
    field_kind,
    scalar_type,
    union_members,
    unwrap_optional,
)
from .inventory import OperationInventory
from .ir import FlagKind, ModelField, ModelSchema


def _model_doc(cls: type[BaseModel]) -> str:
    """The model's schema-level description from its class docstring.

    openapi-generator writes the OpenAPI component `description` as the class
    docstring; for a description-less schema it writes the bare class name. The
    latter is noise, so drop it. Whitespace (the indented triple-quote block) is
    collapsed to a single line.
    """
    doc = (cls.__doc__ or "").strip()
    if not doc or doc == cls.__name__:
        return ""
    return " ".join(doc.split())


def _resolve_ref(tp: object) -> tuple[str | None, bool, list[str] | None]:
    """(model_ref, model_ref_list, variant_refs) for a field annotation."""
    base = unwrap_optional(tp)
    origin = typing.get_origin(base)
    if origin in (list, set):
        args = typing.get_args(base)
        inner = unwrap_optional(args[0]) if args else None
        if isinstance(inner, type) and issubclass(inner, BaseModel):
            return inner.__name__, True, None
        return None, False, None
    if isinstance(base, type) and issubclass(base, BaseModel):
        # a oneOf wrapper class is still a single model_ref (its variants live in
        # its own ModelSchema); an inline Union[...] of models is variant_refs.
        return base.__name__, False, None
    if origin in (typing.Union, UnionType):
        members = [
            a
            for a in typing.get_args(base)
            if isinstance(a, type) and issubclass(a, BaseModel)
        ]
        if len(members) >= 2:
            return None, False, [m.__name__ for m in members]
    return None, False, None


def _model_to_schema(
    cls: type[BaseModel],
) -> tuple[ModelSchema, list[type[BaseModel]]]:
    """Build one ModelSchema; return it + the child model classes to recurse into."""
    children: list[type[BaseModel]] = []
    members = union_members(cls)
    if members:
        ns = sys.modules[cls.__module__]
        fields: list[ModelField] = []
        for name in members:
            member_cls = getattr(ns, name, None)
            if isinstance(member_cls, type) and issubclass(member_cls, BaseModel):
                fields.append(
                    ModelField(
                        name=name,
                        alias=name,
                        py_type=name,
                        kind="json",
                        required=True,
                        model_ref=name,
                    )
                )
                children.append(member_cls)
        schema = ModelSchema(fields=fields, is_oneof=True, description=_model_doc(cls))
        return schema, children

    fields = []
    for fname, f in cls.model_fields.items():
        if fname == "additional_properties":
            continue
        tp = f.annotation
        kind = typing.cast(FlagKind, field_kind(tp))
        ref, ref_list, variants = _resolve_ref(tp)
        examples = getattr(f, "examples", None)
        example = examples[0] if examples else None
        fields.append(
            ModelField(
                name=fname,
                alias=f.alias or fname,
                py_type=str(tp) if kind == "json" else scalar_type(tp),
                kind=kind,
                required=f.is_required(),
                description=f.description or "",
                enum_values=enum_values(unwrap_optional(tp)),
                default=None if f.is_required() else f.default,
                example=example,
                model_ref=ref,
                model_ref_list=ref_list,
                variant_refs=variants,
            )
        )
        base = unwrap_optional(tp)
        origin = typing.get_origin(base)
        if origin in (list, set):
            args = typing.get_args(base)
            base = unwrap_optional(args[0]) if args else None
        if isinstance(base, type) and issubclass(base, BaseModel):
            children.append(base)
        for vname in variants or []:
            vcls = getattr(sys.modules[cls.__module__], vname, None)
            if isinstance(vcls, type) and issubclass(vcls, BaseModel):
                children.append(vcls)
    return ModelSchema(fields=fields, description=_model_doc(cls)), children


def registry_from_models(roots: list[type[BaseModel]]) -> dict[str, ModelSchema]:
    """Deduped registry of every model reachable from ``roots``.

    Keyed by ``cls.__name__``; assumes globally-unique model class names (true for
    openapi-generator single-`models`-module output). A future multi-spec product
    with colliding names would need module-qualified keys.
    """
    registry: dict[str, ModelSchema] = {}
    queue = list(roots)
    while queue:
        cls = queue.pop()
        if cls.__name__ in registry:
            continue
        schema, children = _model_to_schema(cls)
        registry[cls.__name__] = schema  # emit once → cycle-safe
        queue.extend(children)
    return registry


def _root_models(package: str, inv: OperationInventory) -> list[type[BaseModel]]:
    """Resolve the body-model classes named in the inventory to live classes."""
    names: set[str] = set()
    for op in inv.operations:
        names.update(op.body_fields.keys())
    models_mod = importlib.import_module(f"{package}.models")
    roots: list[type[BaseModel]] = []
    for name in sorted(names):
        cls = getattr(models_mod, name, None)
        if isinstance(cls, type) and issubclass(cls, BaseModel):
            roots.append(cls)
    return roots


def build_model_registry(
    package: str, sdk_path: Path, inv: OperationInventory
) -> dict[str, ModelSchema]:
    added = str(sdk_path) not in sys.path
    if added:
        sys.path.insert(0, str(sdk_path))
    try:
        return registry_from_models(_root_models(package, inv))
    finally:
        if added and str(sdk_path) in sys.path:
            sys.path.remove(str(sdk_path))
