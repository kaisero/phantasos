"""SDK operation-override helpers + object-granular wrapper render context.

This module provides build-time validation and resolution of the ``operations:``
block in a product's ``sdk.yml`` (each override keyed by ``resource.method``,
matching the ``OperationInventory`` introspection key), and — building on it —
the in-memory render context that decides which typed
``client.<object>.<verb>(...)`` wrapper classes a built SDK should expose.

The wrapper context is grouped by the **classified object** (``classify_name``'s
object noun), not by the raw ``op.resource`` api-class attribute: one ``*Api``
class typically backs several objects (e.g. ``AccessAndDataPolicyApi`` →
``access_and_data_rule`` / ``access_and_data_section`` / ``access_and_data_policy``).
Each object's methods union the params of every backing raw op (multi-binding), so
``application.get`` collapses ``get_application_by_id`` and
``get_application_by_type_and_id`` into one wrapper method with two ``Binding``s.

``ParamView`` annotations are derived from the **live introspected types** (the
SDK is importable at wrapper-gen time), never from ``ParamInfo.annotation`` (a
debug repr like ``<enum '...'>`` that is unparseable).
"""

from __future__ import annotations

import importlib
import typing
from dataclasses import dataclass
from types import UnionType
from typing import TYPE_CHECKING, Any

from ..opmodel.classify import (
    OBJECT_OF,
    _strip_id_suffix,
    classify_name,
)

if TYPE_CHECKING:
    from phantasos.config import OperationOverride
    from phantasos.generator.opmodel.inventory import (
        OperationInfo,
        OperationInventory,
    )

# OpenAPI Generator names a PUT full-replace as ``update_*`` (no PATCH twin); these
# classify to None, and their cleaned wrapper method is always ``replace``.
_PUT_PREFIX = "update_"

# Scalar live types -> render expression.
_SCALARS: dict[Any, str] = {str: "str", int: "int", bool: "bool", float: "float"}


def validate_override_keys(
    inv: OperationInventory,
    overrides: dict[str, OperationOverride],
) -> None:
    """Raise ``ValueError`` if any override key is not a valid ``resource.method``.

    Args:
        inv: The introspected OperationInventory.
        overrides: Mapping of ``"resource.method"`` to OperationOverride instances.

    Raises:
        ValueError: When one or more keys in *overrides* do not match any
            operation in *inv*.
    """
    keys = {f"{op.resource}.{op.method}" for op in inv.operations}
    unknown = set(overrides) - keys
    if unknown:
        raise ValueError(
            "sdk.yml operations: unknown operation key(s): "
            f"{', '.join(sorted(unknown))}"
        )


# --------------------------------------------------------------------------- #
# Render-context dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class ParamView:
    """One render-ready parameter of a wrapper method.

    ``py_annotation``/``import_from`` are derived from the LIVE introspected type
    (e.g. ``"DeviceGroupPlatform | None"`` + ``("models.device_group_platform",
    "DeviceGroupPlatform")``), never from ``ParamInfo.annotation``.
    """

    name: str
    raw_name: str
    py_annotation: str
    import_from: tuple[str, str] | None
    optional: bool
    default_repr: str
    location: str
    is_enum: bool
    enum_cls: str | None


@dataclass(frozen=True)
class Binding:
    """One raw op backing a (possibly multi-binding) wrapper method."""

    raw_method: str
    requires: tuple[str, ...]
    serialize_name: str


@dataclass
class MethodView:
    """One typed wrapper method on an object (``client.<object>.<name>(...)``)."""

    name: str
    verb: str
    params: list[ParamView]
    body: ParamView | None
    return_model: str
    return_import: tuple[str, str] | None
    bindings: list[Binding]
    is_list: bool
    get_unwrap: bool


@dataclass
class ObjectView:
    """A typed wrapper class for one classified object.

    ``api_attr`` is the backing ``_RESOURCES`` key (the api-class attr) — used by
    the facade pass-2 wiring and the ``_WRAPPERS`` registry.
    """

    attr: str
    classname: str
    api_cls: str
    api_module: str
    api_attr: str
    methods: list[MethodView]
    imports: set[tuple[str, str]]


# --------------------------------------------------------------------------- #
# Object resolution (classified object, override-aware, none-classified anchors)
# --------------------------------------------------------------------------- #


def _crud_objects_by_api(inv: OperationInventory) -> dict[str, set[str]]:
    """Per api-class, the CRUD object attrs (snake).

    These are the anchors that None-classified (non-CRUD / PUT) ops attach to via
    verb-token stripping. ``OBJECT_OF`` returns None for non-CRUD AND for any
    ``_SKIP_FRAGMENTS`` method (e.g. ``*_positions``), so junk objects never leak
    into the anchor set.
    """
    out: dict[str, set[str]] = {}
    for op in inv.operations:
        obj = OBJECT_OF(op.method)
        if obj is not None:
            out.setdefault(op.resource, set()).add(obj.replace("-", "_"))
    return out


def _resolve_object(
    op: OperationInfo,
    crud_objs: dict[str, set[str]],
    ov: OperationOverride | None,
) -> str:
    """Object attr (snake) for ANY op.

    Override wins; else CRUD via ``OBJECT_OF``; else (None-classified) the longest
    CRUD object on the SAME api class whose noun the method ends with; else
    BUILD-FAIL demanding an ``sdk.yml operations`` entry.
    """
    if ov and ov.resource:
        return ov.resource.replace("-", "_")
    obj = OBJECT_OF(op.method)
    if obj is not None:
        return obj.replace("-", "_")
    stem = _strip_id_suffix(op.method)
    for cobj in sorted(crud_objs.get(op.resource, ()), key=len, reverse=True):
        for tail in _noun_tails(cobj):
            if stem.endswith(tail):
                return cobj
    raise ValueError(
        f"None-classified op {op.resource}.{op.method!r} maps to no CRUD object on "
        f"its api class (candidates: {sorted(crud_objs.get(op.resource, ()))}). Add "
        f"`sdk.yml operations: {{'{op.resource}.{op.method}': "
        f"{{resource: <object>, method: <verb>}}}}`."
    )


def _noun_tails(obj_snake: str) -> tuple[str, ...]:
    """The trailing-noun forms a method may end with for object *obj_snake*.

    ``device`` -> ``_device`` / ``_devices``; ``policy`` -> ``_policy`` /
    ``_policies`` (so a plural-with-``y`` action can still attach to its object).
    """
    tails = ["_" + obj_snake, "_" + obj_snake + "s"]
    if obj_snake.endswith("y"):
        tails.append("_" + obj_snake[:-1] + "ies")
    return tuple(tails)


def _verb_phrase(method: str, obj_snake: str) -> str:
    """Clean wrapper-method name for a None-classified op.

    PUT ``update_*`` -> ``replace``; else strip the trailing object noun (and any
    ``_by_id`` / ``_by_type_and_id`` tail) from the method:
    ``suspend_devices``/``device`` -> ``suspend``;
    ``bulk_create_applications``/``application`` -> ``bulk_create``;
    ``revoke_user_request``/``user_request`` -> ``revoke``;
    ``publish_draft_configuration``/``configuration`` -> ``publish_draft``.
    """
    if method.startswith(_PUT_PREFIX):
        return "replace"
    stem = _strip_id_suffix(method)
    for tail in _noun_tails(obj_snake):
        if stem.endswith(tail):
            return stem[: -len(tail)]
    return stem


def _clean_verb_and_method(
    op: OperationInfo,
    overrides: dict[str, OperationOverride],
    crud_objs: dict[str, set[str]],
) -> tuple[str, str, str]:
    """Return ``(object_attr_snake, cli_verb, clean_method_name)``.

    Branch on whether the op is classifiable FIRST — eagerly indexing the
    get/list sub-verb map for a None-classified op would ``KeyError``.
    """
    ov = overrides.get(f"{op.resource}.{op.method}")
    obj = _resolve_object(op, crud_objs, ov)
    c = classify_name(op.method)
    if c is not None:
        verb = ov.verb if (ov and ov.verb) else c.verb
        base = {"get": "get", "list": "list"}[c.sub_verb] if verb == "show" else verb
        method = ov.method if (ov and ov.method) else base
        return obj, verb, method
    # None-classified (PUT replace / verb-phrase action).
    method = ov.method if (ov and ov.method) else _verb_phrase(op.method, obj)
    verb = ov.verb if (ov and ov.verb) else "request"
    return obj, verb, method


# --------------------------------------------------------------------------- #
# Live-type annotation rendering
# --------------------------------------------------------------------------- #


def _render_annotation(
    live_type: object, package: str
) -> tuple[str, tuple[str, str] | None, bool]:
    """From a real type object -> (render expr, import or None, optional).

    Unwraps ``Annotated[T, ...]`` and ``Optional[T]`` / ``T | None``. A type from
    the SDK package renders as its bare qualname with an import; scalars render to
    their builtin name; everything else (datetime, UUID, …) falls back to ``str``.
    """
    tp = live_type
    if typing.get_origin(tp) is typing.Annotated:
        tp = typing.get_args(tp)[0]
    optional = False
    if typing.get_origin(tp) in (typing.Union, UnionType):
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        optional = len(args) < len(typing.get_args(tp))
        tp = args[0] if len(args) == 1 else tp
    if isinstance(tp, type) and tp.__module__.startswith(package):
        expr = tp.__qualname__ + (" | None" if optional else "")
        rel_module = tp.__module__.split(".", 1)[1]
        return expr, (rel_module, tp.__qualname__), optional
    base = _SCALARS.get(tp, "str")
    return (base + " | None") if optional else base, None, optional


def _live_methods(package: str, sdk_path_attr: dict[str, str]) -> dict[str, type[Any]]:
    """Import the SDK api classes keyed by module attr (e.g. ``applications_api``)."""
    out: dict[str, type[Any]] = {}
    for module, cls in sdk_path_attr.items():
        mod = importlib.import_module(f"{package}.api.{module}")
        out[module] = getattr(mod, cls)
    return out


def _hints_for(api_cls: type[Any], raw_method: str) -> dict[str, Any]:
    """Live (extras-stripped) type hints for one raw method, keyed by param name."""
    fn = getattr(api_cls, raw_method)
    try:
        return typing.get_type_hints(fn, include_extras=False)
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# Method assembly (multi-binding param union)
# --------------------------------------------------------------------------- #


def _required_path_params(op: OperationInfo) -> tuple[str, ...]:
    return tuple(
        sorted(p.name for p in op.params if p.location == "path" and p.required)
    )


def _param_view(
    pname: str,
    op_param: Any,
    live_type: object,
    package: str,
    *,
    force_optional: bool,
) -> ParamView:
    expr, import_from, type_optional = _render_annotation(live_type, package)
    optional = force_optional or type_optional or not op_param.required
    is_enum = bool(op_param.enum_values)
    enum_cls = import_from[1] if (is_enum and import_from) else None
    if optional and not expr.endswith(" | None"):
        expr = expr + " | None"
    return ParamView(
        name=pname,
        raw_name=op_param.name,
        py_annotation=expr,
        import_from=import_from,
        optional=optional,
        default_repr="None",
        location=op_param.location,
        is_enum=is_enum,
        enum_cls=enum_cls,
    )


def _build_method(
    method: str,
    verb: str,
    ops: list[OperationInfo],
    api_by_attr: dict[str, type[Any]],
    api_attr_of: dict[str, str],
    package: str,
) -> tuple[MethodView, set[tuple[str, str]]]:
    """Union the params across *ops* into one MethodView; one Binding per op.

    Every unioned non-body param is forced optional (multi-binding: a param
    required by op A may be absent for op B). Body params are renamed to ``body``
    (raw name retained). Annotations come from the live method hints.
    """
    is_list = method == "list"
    imports: set[tuple[str, str]] = set()
    params: list[ParamView] = []
    seen: set[str] = set()
    body: ParamView | None = None
    bindings: list[Binding] = []
    return_model = ""
    return_import: tuple[str, str] | None = None

    for op in ops:
        api_cls = api_by_attr[api_attr_of[op.resource]]
        hints = _hints_for(api_cls, op.method)
        bindings.append(
            Binding(
                raw_method=op.method,
                requires=_required_path_params(op),
                serialize_name=f"_{op.method}_serialize",
            )
        )
        # return model/import from the first op that has one.
        if not return_model and op.return_model:
            return_model = op.return_model
            _, ret_imp, _ = _render_annotation(hints.get("return"), package)
            return_import = ret_imp
            if ret_imp:
                imports.add(ret_imp)
        for op_param in op.params:
            live_type = hints.get(op_param.name)
            if op_param.location == "body":
                pv = _param_view(
                    "body", op_param, live_type, package, force_optional=False
                )
                if pv.import_from:
                    imports.add(pv.import_from)
                if body is None:
                    body = pv
                continue
            if op_param.name in seen:
                continue
            seen.add(op_param.name)
            pv = _param_view(
                op_param.name, op_param, live_type, package, force_optional=True
            )
            if pv.import_from:
                imports.add(pv.import_from)
            params.append(pv)

    mv = MethodView(
        name=method,
        verb=verb,
        params=params,
        body=body,
        return_model=return_model,
        return_import=return_import,
        bindings=bindings,
        is_list=is_list,
        get_unwrap=method == "get",
    )
    return mv, imports


# --------------------------------------------------------------------------- #
# Naming + collision gate
# --------------------------------------------------------------------------- #


def _classname(attr_snake: str) -> str:
    """snake_case object attr -> PascalCase wrapper class name (+ ``Wrapper``)."""
    return "".join(part.title() for part in attr_snake.split("_")) + "Wrapper"


def _gate_collisions(objects: list[ObjectView]) -> None:
    """Raise on a duplicate method name within any one ObjectView."""
    for ov in objects:
        seen: set[str] = set()
        for mv in ov.methods:
            if mv.name in seen:
                raise ValueError(
                    f"object {ov.attr!r}: method name collision on {mv.name!r}"
                )
            seen.add(mv.name)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def build_wrapper_context(
    inv: OperationInventory,
    overrides: dict[str, OperationOverride],
    discovered: list[dict[str, str]],
) -> list[ObjectView]:
    """Build the object-granular wrapper render context for a built SDK.

    Groups ops by their CLASSIFIED object (override > CRUD ``OBJECT_OF`` >
    none-classified verb-token anchor), unions each (object, method)'s ops into a
    multi-binding ``MethodView``, resolves each object's backing api class by
    joining ``op.resource`` against *discovered*, and gates duplicate method names.

    Args:
        inv: The introspected OperationInventory.
        overrides: ``sdk.yml`` ``operations:`` block (``resource.method`` ->
            OperationOverride). May create/target an object with no CRUD anchor.
        discovered: ``_discover_resources`` output: ``[{attr, module, cls}]``.

    Raises:
        ValueError: unknown override key; a None-classified anchorless op with no
            override; an object spanning api classes; a method-name collision.
    """
    validate_override_keys(inv, overrides)
    by_attr = {d["attr"]: d for d in discovered}
    crud_objs = _crud_objects_by_api(inv)

    method_ops: dict[tuple[str, str], list[OperationInfo]] = {}
    obj_api: dict[str, str] = {}
    obj_verb: dict[tuple[str, str], str] = {}
    for op in inv.operations:
        obj_attr, verb, method = _clean_verb_and_method(op, overrides, crud_objs)
        if obj_attr in obj_api and obj_api[obj_attr] != op.resource:
            raise ValueError(
                f"object {obj_attr!r} spans api classes "
                f"{obj_api[obj_attr]!r} and {op.resource!r} — "
                f"disambiguate via sdk.yml operations"
            )
        obj_api[obj_attr] = op.resource
        method_ops.setdefault((obj_attr, method), []).append(op)
        obj_verb[(obj_attr, method)] = verb

    # Import the api classes once (live-type resolution needs the real methods).
    api_by_attr = _live_methods(
        inv.sdk_package,
        {by_attr[r]["module"]: by_attr[r]["cls"] for r in set(obj_api.values())},
    )
    api_attr_of: dict[str, str] = {r: by_attr[r]["module"] for r in obj_api.values()}

    objects: dict[str, ObjectView] = {}
    for (obj_attr, method), ops in method_ops.items():
        res = obj_api[obj_attr]
        d = by_attr[res]
        ov = objects.setdefault(
            obj_attr,
            ObjectView(
                attr=obj_attr,
                classname=_classname(obj_attr),
                api_cls=d["cls"],
                api_module=d["module"],
                api_attr=res,
                methods=[],
                imports=set(),
            ),
        )
        mv, imports = _build_method(
            method,
            obj_verb[(obj_attr, method)],
            ops,
            api_by_attr,
            api_attr_of,
            inv.sdk_package,
        )
        ov.methods.append(mv)
        ov.imports |= imports

    _gate_collisions(list(objects.values()))
    return list(objects.values())
