"""The ``_idempotency`` metadata producer — strategy auto-selection + build gates.

``resolve_idempotency`` mutates each opted-in :class:`~.wrapper.ObjectView` in
place: it auto-selects the three strategy families (fetch / mutate / materialize)
from the introspected wrapper methods, bakes the per-resource ``_idempotency``
class-var literal (strategy trio + identity/scope/models/id_field/…), adds the
model classes' ``(module, class)`` import pairs, and fails loud (``ValueError``)
on any of the eight build gates. ``referenced_strategies`` then folds every
synced object's trio into the per-family union that ``render.vendor`` uses to
decide which strategy modules to write.

Design of record: spec §5.4 / §5.5 and ADR-0004. Selection precedence per
family is ``resources.<name>.<family>`` → ``defaults.<family>`` → auto-derived.

Note on IR accessors: the wrapper IR (``wrapper.py``) does NOT carry a live body
model, a classified sub-verb, or per-param wire metadata on ``Binding``. So the
producer derives them from what IS on the views — ``MethodView.body.import_from``
/ ``MethodView.return_import`` (``(rel_module, ClassName)``), the binding's raw
method name via ``classify_name`` (``patch_*`` → PATCH, ``update_*`` PUT →
``replace``), and ``ParamView.location`` / ``ParamView.raw_name`` on the list
method — plus a live import of the built package to read ``model_fields``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...config import IdempotencyConfig, IdempotencyDefaults, IdempotencyResource
from ..opmodel.classify import classify_name

if TYPE_CHECKING:
    from .wrapper import MethodView, ObjectView

_FETCH, _MUTATE, _MATERIALIZE = "fetch", "mutate", "materialize"


def referenced_strategies(objects: list[ObjectView]) -> dict[str, set[str]]:
    """The per-family UNION of every synced object's selected strategy.

    After :func:`resolve_idempotency`, returns e.g.
    ``{"fetch": {"list_scan"}, "mutate": {"put_rmw"}, "materialize": {"direct"}}``
    — the exact strategy modules ``render.vendor`` must write. Objects that are
    not synced contribute nothing; empty families stay empty sets.
    """
    out: dict[str, set[str]] = {_FETCH: set(), _MUTATE: set(), _MATERIALIZE: set()}
    for o in objects:
        if not getattr(o, "sync", False):
            continue
        meta = o._idempotency_meta  # type: ignore[attr-defined]
        out[_FETCH].add(meta[_FETCH])
        out[_MUTATE].add(meta[_MUTATE])
        out[_MATERIALIZE].add(meta[_MATERIALIZE])
    return out


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def resolve_idempotency(
    objects: list[ObjectView],
    cfg: IdempotencyConfig,
    package: str,
    dist_root: Path,
    *,
    has_pagination: bool,
) -> None:
    """Bake ``_idempotency`` metadata onto each opted-in ``ObjectView`` in place.

    Sets ``sync=True`` / ``idempotency_literal`` / the model imports on each
    ``resources:`` entry (unless ``sync: false``, which leaves the object off),
    and raises ``ValueError`` — naming the resource + the fix — on any build gate.
    """
    by_attr = {o.attr: o for o in objects}
    unknown = set(cfg.resources) - set(by_attr)
    if unknown:
        raise ValueError(
            "sdk.yml idempotency.resources: unknown resource key(s): "
            f"{', '.join(sorted(unknown))} "
            f"(valid: {', '.join(sorted(by_attr))})"
        )
    # Side-effect: ensure *dist_root* is importable so `_class_from` can resolve
    # the built package's live model classes (for their wire keys / __name__).
    _import_pkg(package, dist_root)
    for attr, rc in cfg.resources.items():
        o = by_attr[attr]
        if not rc.sync:
            o.sync = False
            continue
        meta = _build_meta(o, rc, cfg.defaults, package, has_pagination=has_pagination)
        o.sync = True
        o._idempotency_meta = meta  # type: ignore[attr-defined]
        o.idempotency_literal = _idempotency_literal(meta)


# --------------------------------------------------------------------------- #
# Live-import + small accessors
# --------------------------------------------------------------------------- #


def _import_pkg(package: str, dist_root: Path) -> Any:
    """Import the built package (adding *dist_root* to ``sys.path`` if needed)."""
    root = str(dist_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    return importlib.import_module(package)


def _wire_keys(model_cls: type[Any]) -> list[str]:
    """The wire keys of a pydantic model: ``f.alias or name`` per model field."""
    return [f.alias or name for name, f in model_cls.model_fields.items()]


def _method(o: ObjectView, name: str) -> MethodView | None:
    for m in o.methods:
        if m.name == name:
            return m
    return None


def _class_from(package: str, imp: tuple[str, str] | None) -> type[Any] | None:
    """Resolve the live class named by a ``(rel_module, ClassName)`` import pair.

    The rel module is relative to *package* (e.g. ``models.addresses`` under
    ``prisma_access.objects``), so the full module is ``<package>.<rel_module>``.
    """
    if imp is None:
        return None
    rel_module, cls = imp
    mod = importlib.import_module(f"{package}.{rel_module}")
    got = getattr(mod, cls, None)
    return got if isinstance(got, type) else None


def _rel_import(imp: tuple[str, str]) -> tuple[str, str]:
    """Pass a ``(rel_module, ClassName)`` pair through unchanged.

    Body/return imports come from :func:`wrapper._render_annotation`, which already
    strips the package prefix (``prisma_access.objects.models.addresses`` ->
    ``models.addresses``) so ``resources.py`` can emit ``from ..models.addresses``.
    These land in ``o.imports`` alongside the wrapper's own param/return imports,
    which follow the exact same package-relative convention; prepending the package
    here would emit a broken ``from ..prisma_access.objects.models.addresses``.
    """
    return imp


def _body_import(method: MethodView | None) -> tuple[str, str] | None:
    """The ``(rel_module, ClassName)`` of a method's body model, or ``None``."""
    if method is None or method.body is None:
        return None
    return method.body.import_from


def _sub_verb(method: MethodView | None) -> str | None:
    """The classified sub-verb of a method's binding (``patch`` / ``create`` /
    ``delete`` / ``get`` / ``list``), from the raw method name. A PUT full-replace
    (``update_*``) is None-classified, so it returns ``None``."""
    if method is None:
        return None
    for b in method.bindings:
        c = classify_name(b.raw_method)
        if c is not None:
            return c.sub_verb
    return None


def _is_query_param(list_method: MethodView | None, wire_field: str) -> bool:
    """Whether *wire_field* is a ``query`` param on the list method's surface."""
    if list_method is None:
        return False
    for p in list_method.params:
        if p.raw_name == wire_field and p.location == "query":
            return True
    return False


def _resolve_strategy(
    family: str,
    resource: IdempotencyResource,
    defaults: IdempotencyDefaults,
    auto: str,
) -> str:
    """Precedence: ``resources.<name>.<family>`` > ``defaults.<family>`` > auto."""
    return getattr(resource, family) or getattr(defaults, family) or auto


# Pagination knobs a list binding might require — never call params. (`id` routes
# to the URL and is likewise excluded where the extra-required set is computed.)
_PAGINATION_PARAMS = {"limit", "offset"}


def _call_params(
    o: ObjectView,
    rc: IdempotencyResource,
    scope_fields: set[str],
    package: str,
    verb_methods: list[tuple[str, MethodView | None]],
) -> dict[str, dict[str, Any]] | None:
    """Detect per-verb extra-required call params + fold in config defaults.

    A verb's hard-required params are the INTERSECTION of its bindings'
    ``requires`` (with several bindings, ``_select`` needs only one satisfiable).
    Anything beyond the scope fields, the ``id`` routing param and the pagination
    knobs must be an enum param with >= 2 values the engine can thread at call
    time (e.g. the rulebase ``position`` pre/post query enum) — otherwise the
    resource is undrivable and **gate #8** fails the build loud, replacing the
    old silent "gates-green but undrivable" shape (ztna ``oid`` parent ids).

    Returns the ``params`` meta (``{name: {values, verbs, default}}``) or
    ``None`` when the resource has no extra-required param — the key is then
    ABSENT from the literal, keeping param-less resources byte-identical.
    """
    detected: dict[str, dict[str, Any]] = {}
    for verb, m in verb_methods:
        if m is None or not m.bindings:
            continue
        required = set.intersection(*[set(b.requires) for b in m.bindings])
        extra = required - scope_fields - {"id"} - _PAGINATION_PARAMS
        for name in sorted(extra):
            pv = next((p for p in m.params if p.name == name), None)
            cls = _class_from(package, pv.import_from) if (pv and pv.is_enum) else None
            values = [e.value for e in cls] if cls is not None else []
            if len(values) < 2:
                raise ValueError(
                    f"idempotency: {o.attr}: the {verb} op requires param "
                    f"{name!r}, which is not an enum call param the sync engine "
                    f"can thread — opt out with `sync: false`"
                )
            spec = detected.setdefault(
                name, {"values": values, "verbs": [], "default": None}
            )
            if spec["values"] != values:
                raise ValueError(
                    f"idempotency: {o.attr}: call param {name!r} resolves to "
                    f"different value sets across verbs ({spec['values']} vs "
                    f"{values}) — opt out with `sync: false`"
                )
            spec["verbs"].append(verb)
    unknown = set(rc.params) - set(detected)
    if unknown:
        raise ValueError(
            f"idempotency: {o.attr}: params: {', '.join(sorted(unknown))} not "
            f"required by any of the resource's list/create/update ops — remove "
            f"the entry (detection and values/verbs are auto-derived; config "
            f"only sets the default of a detected param)"
        )
    for name, p in rc.params.items():
        if p.default is not None and p.default not in detected[name]["values"]:
            raise ValueError(
                f"idempotency: {o.attr}: params.{name}.default {p.default!r} is "
                f"not one of the op's enum values {detected[name]['values']}"
            )
        detected[name]["default"] = p.default
    return detected or None


# --------------------------------------------------------------------------- #
# Per-resource metadata + gates
# --------------------------------------------------------------------------- #


def _build_meta(
    o: ObjectView,
    rc: IdempotencyResource,
    defaults: IdempotencyDefaults,
    package: str,
    *,
    has_pagination: bool,
) -> dict[str, Any]:
    """Auto-select the strategy trio + bake the metadata for one synced resource.

    Runs the build gates inline (fail-loud, naming the resource + the fix) and
    adds each model class's full ``(module, class)`` import to ``o.imports``.
    """
    create_m = _method(o, "create")
    read_m = _method(o, "get")
    list_m = _method(o, "list")
    patch_m = _method(o, "update")  # PATCH classifies to the `update` verb
    put_m = _method(o, "replace")  # PUT full-replace -> the `replace` verb
    delete_m = _method(o, "delete")
    update_method = patch_m or put_m

    create_imp = _body_import(create_m)
    update_imp = _body_import(update_method)
    read_imp = read_m.return_import if read_m else None

    create_cls = _class_from(package, create_imp)
    update_cls = _class_from(package, update_imp) or create_cls
    read_cls = _class_from(package, read_imp) or create_cls

    # --- identity (gate #2: unresolvable) --------------------------------- #
    if rc.identity is not None:
        identity = list(rc.identity)
    elif create_cls is not None and "name" in _wire_keys(create_cls):
        identity = ["name"]
    else:
        raise ValueError(
            f"idempotency: {o.attr}: identity could not be inferred (no annotation "
            f"and no `name` on the create model) — add `identity: [...]` or "
            f"`sync: false`"
        )

    # --- update verb (gate #4: no update op) ------------------------------ #
    singleton = rc.singleton
    if update_method is None and not singleton:
        raise ValueError(
            f"idempotency: {o.attr}: no update verb (neither a PATCH `update` nor a "
            "PUT `replace` op) — add an update op, or opt out with `sync: false`"
        )

    # --- singleton sanity (gate #7) --------------------------------------- #
    if singleton and (create_m is not None or delete_m is not None):
        raise ValueError(
            f"idempotency: {o.attr}: `singleton: true` but a create/delete op "
            f"exists — a singleton is neither created nor deleted; drop `singleton` "
            f"or hide those ops"
        )

    # --- scope ------------------------------------------------------------ #
    scope = rc.scope or defaults.scope
    scope_lit = {"fields": list(scope.fields), "rule": scope.rule} if scope else None
    scope_fields = set(scope.fields) if scope else set()

    # --- id_field --------------------------------------------------------- #
    id_wire, id_attr = "id", "id"
    if read_cls is not None:
        for name, f in read_cls.model_fields.items():
            if name == "id" or f.alias == "id":
                id_wire, id_attr = (f.alias or name), name
                break

    # --- strategies ------------------------------------------------------- #
    auto_fetch = "get" if singleton else "list_scan"
    fetch = _resolve_strategy(_FETCH, rc, defaults, auto_fetch)
    if _sub_verb(update_method) == "patch":
        auto_mutate = "patch_minimal"
    elif singleton:
        # A singleton's PUT `replace` binding takes NO `id` — its update-on-drift
        # goes through the id-less `put_singleton` (only PUT singletons exist now;
        # a PATCH singleton would still take the patch_minimal branch above).
        auto_mutate = "put_singleton"
    else:
        auto_mutate = "put_rmw"
    mutate = _resolve_strategy(_MUTATE, rc, defaults, auto_mutate)
    upd_ret = update_method.return_model if update_method else ""
    auto_mat = (
        "direct"
        if (upd_ret and read_cls is not None and upd_ret == read_cls.__name__)
        else "get_after_write"
    )
    materialize = _resolve_strategy(_MATERIALIZE, rc, defaults, auto_mat)

    # --- fetch gates (#3 list_filter query params, #6 pagination) --------- #
    if fetch == "list_filter":
        for idf in identity:
            if not _is_query_param(list_m, idf):
                raise ValueError(
                    f"idempotency: {o.attr}: fetch: list_filter but identity field "
                    f"{idf!r} is not a query param on the list op — set a filterable "
                    f"identity or use the default list_scan fetch"
                )
    if fetch == "list_scan" and not has_pagination:
        raise ValueError(
            f"idempotency: {o.attr}: a list_scan fetch requires a pagination "
            f"component (declare `pagination:` in sdk.yml) — full-scan sync would "
            f"otherwise silently read only the first page"
        )

    # --- extra-required call params (gate #8) + `params` meta ------------- #
    call_params = _call_params(
        o,
        rc,
        scope_fields,
        package,
        [("list", list_m), ("create", create_m)]
        + ([(update_method.name, update_method)] if update_method else []),
    )

    # --- fields + server_only + F6 write-only gate (#5) ------------------- #
    input_fields = sorted(
        (set(_wire_keys(create_cls)) if create_cls else set())
        | (set(_wire_keys(update_cls)) if update_cls else set())
    )
    server_only = sorted(
        {id_wire}
        | set(defaults.read_only)
        | set(defaults.computed)
        | set(rc.read_only)
        | set(rc.computed)
    )
    managed = set(input_fields) - set(server_only) - scope_fields - set(rc.write_only)
    read_keys = set(_wire_keys(read_cls)) if read_cls else set()
    undetectable = sorted(managed - read_keys)
    if undetectable:
        raise ValueError(
            f"idempotency: {o.attr}: managed field(s) {undetectable} are "
            f"undetectable via GET (absent from the read model) — declare them "
            f"under `write_only:` (partial sync) or set `sync: false`"
        )

    hydrate = rc.hydrate if rc.hydrate is not None else (read_m is not None)

    # --- model imports (package-relative, like the wrapper's own) --------- #
    for imp in (create_imp, update_imp, read_imp):
        if imp is not None:
            o.imports.add(_rel_import(imp))

    create_name = (
        create_cls.__name__ if create_cls else (read_cls and read_cls.__name__)
    )
    update_name = update_cls.__name__ if update_cls else create_name
    read_name = read_cls.__name__ if read_cls else create_name
    meta: dict[str, Any] = {
        "identity": identity,
        "scope": scope_lit,
        "models": {
            "create": create_name,
            "update": update_name,
            "read": read_name,
        },
        "input_fields": input_fields,
        "server_only": server_only,
        "id_field": {"wire": id_wire, "attr": id_attr},
        "order_sensitive": list(rc.order_sensitive),
        "write_only": list(rc.write_only),
        "projections": dict(rc.projections),
        "singleton": singleton,
        "update": {"verb": (update_method.name if update_method else "replace")},
        _FETCH: fetch,
        _MUTATE: mutate,
        _MATERIALIZE: materialize,
        "fetch_opts": {"page_limit": rc.page_limit, "hydrate": hydrate},
    }
    # The key is baked ONLY when an extra-required param exists — a param-less
    # resource must regenerate byte-identically (no `params` entry at all).
    if call_params:
        meta["params"] = call_params
    return meta


# --------------------------------------------------------------------------- #
# Literal rendering (mirrors _bindings_literal EXCEPT `models` are bare idents)
# --------------------------------------------------------------------------- #

_ORDER = [
    "identity",
    "scope",
    "params",  # extra-required call params — present only when detected
    "models",
    "input_fields",
    "server_only",
    "id_field",
    "order_sensitive",
    "write_only",
    "projections",
    "singleton",
    "update",
    _FETCH,
    _MUTATE,
    _MATERIALIZE,
    "fetch_opts",
]


def _idempotency_literal(meta: dict[str, Any]) -> str:
    """The ``_idempotency`` class-var body.

    Mirrors ``wrapper._bindings_literal`` (each value ``repr``-ed into a stable
    dict literal) EXCEPT the ``models`` values render as **bare class identifiers**
    (``Addresses``), not ``repr`` strings — so the emitted mixin references the
    live classes imported into ``resources.py``.
    """
    parts = {k: repr(v) for k, v in meta.items()}
    # `models` values are BARE class identifiers (referencing the imported live
    # classes), not repr strings.
    parts["models"] = (
        "{" + ", ".join(f'"{k}": {v}' for k, v in meta["models"].items()) + "}"
    )
    # `params` is optional — absent keys are skipped so a param-less resource's
    # literal stays byte-identical to the pre-`params` output.
    body = ",\n".join(f'        "{k}": {parts[k]}' for k in _ORDER if k in parts)
    return "{\n" + body + "\n    }"
