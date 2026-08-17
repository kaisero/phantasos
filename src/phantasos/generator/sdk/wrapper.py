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
import keyword
import typing
from dataclasses import dataclass
from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, Any

from ..opmodel.classify import (
    OBJECT_OF,
    _strip_id_suffix,
    classify_name,
)
from ..opmodel.introspect import _unwrap_optional
from .docs import _VERB_SLOT
from .examples import assemble_reference_docstring, reference_example

if TYPE_CHECKING:
    from phantasos.config import IdempotencyConfig, OperationOverride
    from phantasos.generator.opmodel.inventory import (
        OperationInfo,
        OperationInventory,
    )

    from ...productconfig import DocsConfig

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
        raise ValueError(f"sdk.yml operations: unknown operation key(s): {', '.join(sorted(unknown))}")


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
    """One raw op backing a (possibly multi-binding) wrapper method.

    The render-prep fields below let the emitted ``_to_raw``/``_select`` stay
    dumb: they describe — for THIS op specifically — how a wrapper call maps onto
    the raw generated method.

    - ``param_map``: ordered ``(wrapper_name, raw_name)`` for every non-body param
      this op accepts. Because a discriminator like ``type`` routes to *path* on
      ``*_by_type`` but *query* on the plain op, the accepted set differs per
      binding — so the routing is captured here, not on the unioned ``ParamView``.
    - ``body_raw``: the op's raw body-param name (``create_or_replace_app_input``),
      so the generated code can rename the wrapper's ``body`` kwarg.
    - ``enum_map``: ``(wrapper_name, EnumClassName)`` for the op's enum params, so
      the generated ``_to_raw`` can coerce a passed enum-string to the enum.
    """

    raw_method: str
    requires: tuple[str, ...]
    serialize_name: str
    param_map: tuple[tuple[str, str], ...] = ()
    body_raw: str | None = None
    enum_map: tuple[tuple[str, str], ...] = ()


@dataclass
class MethodView:
    """One typed wrapper method on an object (``client.<object>.<name>(...)``).

    The structural fields (``params``/``body``/``bindings``…) are produced by
    Task 3.1's assembly; the render-prep strings below are computed once (in
    ``_compute_method_prep``) so the template is a dumb interpolator:

    - ``sig``: the full typed parameter list (every param optional; list adds
      ``*, all_pages: bool = False``).
    - ``return_expr``: the method's annotated return type (``None`` for a
      non-returning op like ``delete``).
    - ``present_expr``: a ``{...}`` set of the wrapper params non-None at call
      time — drives ``_select`` (most-specific binding whose ``requires`` ⊆
      present); single- and multi-binding share this path.
    - ``call_dict``: a ``{...}`` dict of every wrapper param (forwarded to the
      generic ``_call``/``_fetch``/``_list`` helper, which renames + coerces).
    - ``docstring``: one-line summary for the emitted method docstring; for
      single-binding methods taken from the op summary; for multi-binding methods
      synthesized from the verb + object name (e.g. ``"Get a device group."``).
    """

    name: str
    verb: str
    params: list[ParamView]
    body: ParamView | None
    return_model: str
    return_import: tuple[str, str] | None
    bindings: list[Binding]
    is_list: bool
    get_unwrap: bool
    sig: str = ""
    return_expr: str = "None"
    present_expr: str = "set()"
    call_dict: str = "{}"
    docstring: str = ""


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
    bindings_literal: str = "{}"
    # Idempotent-sync metadata (baked by ``idempotency.resolve_idempotency`` when
    # the product opts a resource in). ``sync`` gates the emitted sync mixin;
    # ``idempotency_literal`` is the ``_idempotency`` class-var body (``"{}"`` when
    # the object is not synced — the byte-identical default).
    sync: bool = False
    idempotency_literal: str = "{}"


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
    ``_policies`` (so a plural-with-``y`` action can still attach to its object);
    ``address`` -> ``_address`` / ``_addresses`` (the ``-es`` plural — must mirror
    ``classify._singularize`` so an ``update_addresses_by_id`` PUT anchors to the
    ``address`` object instead of a naive ``_addresss`` that never matches).
    """
    # Additive: keep the singular + naive ``+s`` plural (covers vowel+y like
    # ``gateway`` -> ``gateways``), and ADD the ``-ies`` (consonant+y) and ``-es``
    # (sibilant: s/x/z/ch/sh) plurals so e.g. ``address`` also yields ``addresses``.
    tails = ["_" + obj_snake, "_" + obj_snake + "s"]
    if obj_snake.endswith("y"):
        tails.append("_" + obj_snake[:-1] + "ies")
    if obj_snake.endswith(("s", "x", "z", "ch", "sh")):
        tails.append("_" + obj_snake + "es")
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


def _safe_ident(name: str) -> str:
    """Escape a method name that collides with a Python keyword (``import`` ->
    ``import_``) so the rendered ``def <name>`` is valid Python. PEP 8's
    trailing-underscore keyword-clash convention. Applied to EVERY final method
    name (CRUD verb, verb-phrase action, or an override-provided one) — a verb
    like ``import_certificates`` otherwise verb-phrases to the keyword ``import``
    and emits a ``def import(...)`` syntax error that no override would catch.
    """
    return f"{name}_" if keyword.iskeyword(name) else name


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
    else:
        # None-classified (PUT replace / verb-phrase action).
        method = ov.method if (ov and ov.method) else _verb_phrase(op.method, obj)
        verb = ov.verb if (ov and ov.verb) else "request"
    return obj, verb, _safe_ident(method)


# --------------------------------------------------------------------------- #
# Live-type annotation rendering
# --------------------------------------------------------------------------- #


def _render_annotation(live_type: object, package: str) -> tuple[str, tuple[str, str] | None, bool]:
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
        # Strip the FULL package prefix (not just the first segment): for a
        # federated sub-package `prisma_access.objects` a model module is
        # `prisma_access.objects.models.address` -> `models.address`, so the
        # `from ..models.address import …` in resources.py resolves. A naive
        # `split(".", 1)[1]` would leave `objects.models.address` and emit a
        # broken `from ..objects.models.address`.
        rel_module = tp.__module__[len(package) + 1 :]
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
    return tuple(sorted(p.name for p in op.params if p.location == "path" and p.required))


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


def _article(word: str) -> str:
    """Return ``"an"`` when *word* starts with a vowel sound, else ``"a"``."""
    return "an" if word[:1].lower() in "aeiou" else "a"


def _method_docstring(method: str, obj_attr: str, ops: list[OperationInfo]) -> str:
    """One-line docstring for the emitted wrapper method.

    For a single-binding method the op's own summary is used verbatim (if
    non-empty). For multi-binding methods — or when the single op has no
    summary — a sensible one-liner is synthesized from the verb + object noun
    (e.g. ``"Get a device group."``).

    The canonical verbs ``get``/``list``/``delete``/``create``/``update``/
    ``replace`` produce natural English phrases; all other verbs (custom
    verb-phrase actions) capitalise the method name.
    """
    # Single-binding with a non-empty op summary: use it directly.
    if len(ops) == 1 and ops[0].summary:
        s = ops[0].summary.strip()
        return s if s.endswith(".") else s + "."

    # Synthesize from verb + object noun.
    obj_human = obj_attr.replace("_", " ")
    art = _article(obj_human)
    verb_phrases: dict[str, str] = {
        "get": f"Get {art} {obj_human}.",
        "list": f"List {obj_human}s.",
        "create": f"Create {art} {obj_human}.",
        "update": f"Update {art} {obj_human}.",
        "delete": f"Delete {art} {obj_human}.",
        "replace": f"Replace {art} {obj_human}.",
    }
    if method in verb_phrases:
        return verb_phrases[method]
    # Generic fallback: capitalise the method name and append the object.
    readable = method.replace("_", " ")
    return f"{readable.capitalize()} {obj_human}."


def _req_path_param_count(op: OperationInfo) -> int:
    """Count required PATH params (distinct from the existing ``_required_path_params``,
    which returns the tuple of names — this returns the count for ``min(...)`` keying).
    """
    return sum(1 for p in op.params if p.location == "path" and p.required)


def _reference_example_for(
    method: str,
    obj_attr: str,
    ops: list[OperationInfo],
    body_model: type[Any] | None,
    docs: DocsConfig,
) -> str | None:
    """Compute the reference-example block for one wrapper method, or None."""
    # Illustrate the binding with the fewest required path params (the minimal call).
    # `body_model` comes from the FIRST op carrying a body (captured in
    # `_build_method`), which may differ from `example_op` for a hypothetical
    # multi-binding method that both takes a body AND varies path params across
    # bindings. No such op exists in current products (multi-binding methods are
    # bodyless); revisit this pairing if one appears.
    example_op = min(ops, key=_req_path_param_count)
    path_args: list[tuple[str, str]] = [
        (p.name, p.enum_values[0] if p.enum_values else f"<{p.name}>")
        for p in example_op.params
        if p.location == "path" and p.required
    ]
    # Showcase: honor the configured variant + per-slot verbatim override (D4/D6).
    is_showcase = obj_attr == docs.showcase_resource
    variant = docs.showcase_variant if is_showcase else None
    override = None
    if is_showcase and docs.examples is not None:
        slot = _VERB_SLOT.get(method)
        if slot is not None:
            override = getattr(docs.examples, slot, None)
    return reference_example(
        attr=obj_attr,
        method=method,
        path_args=path_args,
        body_model=body_model,
        variant=variant,
        override=override,
    )


def _build_method(
    method: str,
    verb: str,
    ops: list[OperationInfo],
    api_by_attr: dict[str, type[Any]],
    api_attr_of: dict[str, str],
    package: str,
    obj_attr: str = "",
    *,
    docs: DocsConfig | None = None,
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
    body_model_live: type[Any] | None = None

    for op in ops:
        api_cls = api_by_attr[api_attr_of[op.resource]]
        hints = _hints_for(api_cls, op.method)
        # Per-op mapping wrapper-name -> raw-name + which params are enums + the
        # raw body-param name (THIS op's accepted surface — discriminator routing
        # to path-vs-query is implicit, since the raw method takes every accepted
        # param by keyword regardless of its OpenAPI location).
        op_param_map: list[tuple[str, str]] = []
        op_enum_map: list[tuple[str, str]] = []
        op_body_raw: str | None = None
        for op_param in op.params:
            if op_param.location == "body":
                op_body_raw = op_param.name
                continue
            op_param_map.append((op_param.name, op_param.name))
            if op_param.enum_values:
                _, imp, _ = _render_annotation(hints.get(op_param.name), package)
                if imp:
                    op_enum_map.append((op_param.name, imp[1]))
        bindings.append(
            Binding(
                raw_method=op.method,
                requires=_required_path_params(op),
                serialize_name=f"_{op.method}_serialize",
                param_map=tuple(op_param_map),
                body_raw=op_body_raw,
                enum_map=tuple(op_enum_map),
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
                if body_model_live is None:
                    _unwrapped = _unwrap_optional(live_type)
                    body_model_live = _unwrapped if isinstance(_unwrapped, type) else None
                pv = _param_view("body", op_param, live_type, package, force_optional=False)
                if pv.import_from:
                    imports.add(pv.import_from)
                if body is None:
                    body = pv
                continue
            if op_param.name in seen:
                continue
            seen.add(op_param.name)
            pv = _param_view(op_param.name, op_param, live_type, package, force_optional=True)
            if pv.import_from:
                imports.add(pv.import_from)
            params.append(pv)

    summary = _method_docstring(method, obj_attr, ops)
    docstring = summary
    if docs is not None:
        example = _reference_example_for(method, obj_attr, ops, body_model_live, docs)
        docstring = assemble_reference_docstring(summary, example)

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
        docstring=docstring,
    )
    _compute_method_prep(mv)
    return mv, imports


# --------------------------------------------------------------------------- #
# Render-prep: precomputed strings the template interpolates verbatim
# --------------------------------------------------------------------------- #


def _wrapper_param_names(mv: MethodView) -> list[str]:
    """Every wrapper-call param name (scalar params + ``body`` when present)."""
    names = [p.name for p in mv.params]
    if mv.body is not None:
        names.append("body")
    return names


def _sig_str(mv: MethodView) -> str:
    """The typed parameter list (no leading ``self``).

    Every param is optional with a ``None`` default so the uniform ``_to_raw``
    filter (drop ``None`` kwargs) works; a ``list`` method also appends the
    keyword-only ``all_pages`` toggle.
    """
    parts = [f"{p.name}: {p.py_annotation} = None" for p in mv.params]
    if mv.body is not None:
        ann = mv.body.py_annotation
        if not ann.endswith(" | None"):
            ann = ann + " | None"
        parts.append(f"body: {ann} = None")
    if mv.is_list:
        parts.append("*, all_pages: bool = False")
    return ", ".join(parts)


def _present_expr(mv: MethodView) -> str:
    """A ``{...}`` set literal of the wrapper params that are non-None at call time.

    Drives ``_select`` (most-specific binding whose ``requires`` are all present).
    """
    names = _wrapper_param_names(mv)
    if not names:
        # No params -> an always-empty set. Emit a typed `set[str]()` rather than
        # `{k for k, v in {}.items() ...}`: mypy can't infer k/v over an empty dict
        # literal and reports `var-annotated`.
        return "set[str]()"
    inner = ", ".join(f'"{n}": {n}' for n in names)
    return "{k for k, v in {" + inner + "}.items() if v is not None}"


def _call_kwargs(mv: MethodView) -> str:
    """A ``{...}`` dict literal mapping wrapper-param name -> its local value."""
    names = _wrapper_param_names(mv)
    return "{" + ", ".join(f'"{n}": {n}' for n in names) + "}"


def _compute_method_prep(mv: MethodView) -> None:
    """Populate the render-ready strings on *mv* (mutates in place).

    Every method body is a uniform one-line delegation keyed on the precomputed
    ``present_expr`` (non-None wrapper args) + ``call_dict`` (all wrapper args);
    the emitted ``_select`` resolves the most-specific binding (single- AND
    multi-binding share this path — a single binding is just a one-candidate
    select). ``list`` adds the ``all_pages`` toggle; ``get`` unwraps via
    ``_fetch``.
    """
    mv.sig = _sig_str(mv)
    mv.return_expr = mv.return_model if mv.return_model else "None"
    mv.present_expr = _present_expr(mv)
    mv.call_dict = _call_kwargs(mv)


def _binding_dict_repr(b: Binding) -> str:
    """A ``repr``-able dict literal for one binding (used in ``_bindings``)."""
    return repr(
        {
            "raw_method": b.raw_method,
            "serialize_name": b.serialize_name,
            "requires": list(b.requires),
            "param_map": dict(b.param_map),
            "body": b.body_raw,
            "enums": dict(b.enum_map),
        }
    )


def _bindings_literal(methods: list[MethodView]) -> str:
    """The ``_bindings`` class-var dict literal: ``verb -> [binding-dict, ...]``."""
    items = []
    for mv in methods:
        binds = ", ".join(_binding_dict_repr(b) for b in mv.bindings)
        items.append(f'    "{mv.name}": [{binds}],')
    return "{\n" + "\n".join(items) + "\n    }"


# --------------------------------------------------------------------------- #
# Naming + collision gate
# --------------------------------------------------------------------------- #


def _classname(attr_snake: str) -> str:
    """snake_case object attr -> PascalCase resource class name (+ ``Resource``).

    e.g. ``application`` -> ``ApplicationResource``, ``device_group`` ->
    ``DeviceGroupResource``. The emitted class is ``<Object>Resource``.
    """
    return "".join(part.title() for part in attr_snake.split("_")) + "Resource"


def _gate_collisions(objects: list[ObjectView]) -> None:
    """Raise on a duplicate method name within any one ObjectView."""
    for ov in objects:
        seen: set[str] = set()
        for mv in ov.methods:
            if mv.name in seen:
                raise ValueError(f"object {ov.attr!r}: method name collision on {mv.name!r}")
            seen.add(mv.name)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def build_wrapper_context(
    inv: OperationInventory,
    overrides: dict[str, OperationOverride],
    discovered: list[dict[str, str]],
    *,
    docs: DocsConfig | None = None,
    idempotency: IdempotencyConfig | None = None,
    dist_root: Path | None = None,
    has_pagination: bool = False,
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
        docs: When provided, every ``MethodView.docstring`` is extended with a
            synthesized ``**Example:**`` block via ``assemble_reference_docstring``.
        idempotency: When provided, ``resolve_idempotency`` bakes the per-resource
            ``_idempotency`` metadata (strategy trio + models + gates) onto each
            opted-in ``ObjectView`` (``sync``/``idempotency_literal``/``imports``).
            ``None`` (the default) leaves every object un-synced and byte-identical.
        dist_root: The ``sys.path`` root under which the built package's live model
            classes import (required when *idempotency* is set).
        has_pagination: Whether the product ships a pagination component — drives
            the F8 ``list_scan`` gate in the idempotency producer.

    Raises:
        ValueError: unknown override key; a None-classified anchorless op with no
            override; an object spanning api classes; a method-name collision; or
            any of the seven idempotency build gates (when *idempotency* is set).
    """
    validate_override_keys(inv, overrides)
    by_attr = {d["attr"]: d for d in discovered}
    crud_objs = _crud_objects_by_api(inv)

    method_ops: dict[tuple[str, str], list[OperationInfo]] = {}
    obj_api: dict[str, str] = {}
    obj_verb: dict[tuple[str, str], str] = {}
    for op in inv.operations:
        # `sdk.yml operations: <op>: {hide: true}` drops the op from the wrapper.
        # This `continue` MUST run BEFORE `_clean_verb_and_method` → `_resolve_object`,
        # which raises synchronously for a None-classified anchorless op: a hidden op
        # (e.g. a multipart upload with no body, or a full-replace PUT) is precisely
        # the kind that would otherwise trip that gate, so suppressing it here lets it
        # be dropped silently instead of failing the build.
        op_ov = overrides.get(f"{op.resource}.{op.method}")
        if op_ov is not None and op_ov.hide:
            continue
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
            obj_attr,
            docs=docs,
        )
        ov.methods.append(mv)
        ov.imports |= imports

    result = list(objects.values())
    _gate_collisions(result)
    for ov in result:
        ov.methods.sort(key=lambda m: m.name)
        ov.bindings_literal = _bindings_literal(ov.methods)
    if idempotency is not None:
        from .idempotency import resolve_idempotency

        resolve_idempotency(
            result,
            idempotency,
            inv.sdk_package,
            dist_root if dist_root is not None else Path.cwd(),
            has_pagination=has_pagination,
        )
    return result
