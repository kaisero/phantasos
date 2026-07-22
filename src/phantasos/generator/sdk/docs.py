"""Wrapper-driven docs context for generated SDKs.

The docs feature tailors its how-to guides to one author-named **showcase
object** — a `client.<object>` typed wrapper (e.g. `client.application`). The
guides teach the wrapper surface (`client.<object>.<clean_verb>(...)`), never the
raw `*Api`. We introspect the SDK's `_WRAPPERS` registry (via `cli_operations`,
which already stamps each op with its `object_attr`/`clean_method`/`has_body`
routing) and read the wrapper's clean CRUD verbs directly — no raw-prefix verb
heuristic. The wrapper already canonicalized create/get/list/update/delete, so
the showcase slots ARE those methods.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from ...productconfig import DocsExamples, LoadedProduct
    from ..cli.inventory import OperationInfo, OperationInventory

# Clean wrapper verb -> CRUD slot. The wrapper canonicalizes verbs, so this is a
# direct map (no token-stripping / fewest-params heuristic). Wrapper methods
# outside this set (`replace`/`reorder`/`publish`/`bulk_*`) are not CRUD slots and
# are left out of the showcase (the guide focuses on the 5 CRUD operations).
_VERB_SLOT = {
    "create": "create",
    "get": "read",
    "list": "list",
    "update": "update",
    "delete": "delete",
}


def classify_operations(operations: list[OperationInfo], obj: str) -> dict[str, OperationInfo]:
    """Map each CRUD slot to the wrapper op (clean verb) for `obj` (present only).

    `operations` is the `cli_operations` inventory (each op stamped with
    `object_attr`/`clean_method`). We select the ops whose `object_attr` is the
    showcase object and whose `clean_method` is a CRUD verb, keyed by slot. When a
    clean verb has several bindings (e.g. `application.get` via id or type+id), the
    object+verb pair is identical across them — pick the binding with the FEWEST
    required path params so the example stays minimal (`get(id=...)` over
    `get(type=..., id=...)`).
    """
    slots: dict[str, OperationInfo] = {}
    for op in operations:
        if op.object_attr != obj or op.clean_method is None:
            continue
        slot = _VERB_SLOT.get(op.clean_method)
        if slot is None:
            continue
        existing = slots.get(slot)
        if existing is None or _required_path_count(op) < _required_path_count(existing):
            slots[slot] = op
    return slots


def _required_path_count(op: OperationInfo) -> int:
    return sum(1 for p in op.params if p.location == "path" and p.required)


def _op_dict(
    op: OperationInfo,
    resolve: Callable[[str], type | None] | None,
    variant: str | None,
) -> dict[str, object]:
    """Per-slot example data for the WRAPPER call shape.

    The wrapper method takes its request body under the kwarg `body` (not the raw
    body-param name) plus any required path params (e.g. `id`, `type`). We emit:
    - a `body` arg (kind="body") whose `body_code` is the synthesized model expr,
      when the binding carries a request body (`op.has_body`);
    - one path arg per required path param (kind="path").
    """
    from .examples import synthesize_body

    required_args: list[dict[str, object]] = []
    for p in op.params:
        if not p.required:
            continue
        if p.location == "path":
            placeholder = p.enum_values[0] if p.enum_values else f"<{p.name}>"
            required_args.append({"name": p.name, "kind": "path", "placeholder": str(placeholder)})
    if op.has_body:
        body_param = next((p for p in op.params if p.location == "body"), None)
        body_model = body_param.body_model if body_param else None
        cls = resolve(body_model) if (resolve and body_model) else None
        body_code = synthesize_body(cls, variant=variant) if cls is not None else f"{body_model}(...)"
        required_args.append(
            {
                "name": "body",
                "kind": "body",
                "body_model": body_model,
                "body_code": body_code,
            }
        )
    return {
        # `method` is the CLEAN wrapper verb (drives `client.<object>.<method>`).
        "method": op.clean_method,
        "summary": op.summary,
        "description": op.description,
        "required_args": required_args,
        "return_model": op.return_model,
        "items_field": op.items_field,
    }


def shape_context(
    inventory: OperationInventory,
    *,
    obj: str,
    site_name: str,
    auth: object | None,
    has_pagination: bool,
    resolve: Callable[[str], type | None] | None = None,
    variant: str | None = None,
    examples: DocsExamples | None = None,
    subpackage: str | None = None,
) -> dict[str, object]:
    slots = classify_operations(inventory.operations, obj)
    operations = {slot: _op_dict(op, resolve, variant) for slot, op in slots.items()}
    ex = vars(examples) if examples else {}
    for slot, entry in operations.items():
        entry["example_override"] = ex.get(slot)
    showcase = {
        # `attr` is the singular `client.<object>` wrapper attribute (a clean Python
        # identifier). `call_path` is what the guides render after `client.` — equal
        # to `attr` for single-spec, but `<sub>.<object>` for a federated sub-package
        # (e.g. `objects.address`) so the example reads `client.objects.address.<v>`.
        "attr": obj,
        "call_path": f"{subpackage}.{obj}" if subpackage else obj,
        "operations": operations,
        "has_create": "create" in operations,
        "has_read": "read" in operations,
        "has_list": "list" in operations,
        "has_update": "update" in operations,
        "has_delete": "delete" in operations,
        "list": operations.get("list"),
    }
    credentials = []
    if auth is not None and hasattr(auth, "credential_fields"):
        for f in auth.credential_fields():
            credentials.append(
                {
                    "name": f.name,
                    "env_var": f.env_var,
                    "secret": f.secret,
                    "required": f.required,
                }
            )
    return {
        "has_docs": True,
        "site_name": site_name,
        "showcase": showcase,
        "credentials": credentials,
        "show_pagination_guide": has_pagination and showcase["has_list"],
    }


def _wrapper_objects(package: str, project_dir: Path) -> list[str]:
    """The `_WRAPPERS` object keys of the built SDK (for fail-fast validation)."""
    import importlib
    import sys

    added = str(project_dir) not in sys.path
    if added:
        sys.path.insert(0, str(project_dir))
    try:
        facade = importlib.import_module(f"{package}.extras.facade")
        return list(facade._WRAPPERS)
    finally:
        if added and str(project_dir) in sys.path:
            sys.path.remove(str(project_dir))


def _validate_object(available: list[str], obj: str) -> None:
    if obj not in available:
        raise ValueError(
            f"docs.showcase_resource {obj!r} is not a wrapper object; available objects: {sorted(available)}"
        )


def build_docs_context(loaded: LoadedProduct, project_dir: Path) -> dict[str, object]:
    """Wrapper introspect of the showcase object -> docs context dict."""
    import importlib

    from ..cli.classify import cli_operations

    cfg = loaded.config
    if cfg.docs is None:  # guarded by the caller; this is a defensive check
        raise AssertionError("build_docs_context called without a docs config")
    obj = cfg.docs.showcase_resource
    # Federated products carry the facade/IR/models under `<package>.<sub>.*`; a
    # single-spec product keeps them at the root (`showcase_pkg == cfg.package`).
    sub = cfg.docs.showcase_subpackage
    showcase_pkg = f"{cfg.package}.{sub}" if sub else cfg.package
    _validate_object(_wrapper_objects(showcase_pkg, project_dir), obj)
    inventory = cli_operations(showcase_pkg, project_dir)
    site_name = cfg.docs.site_name or loaded.context.get("distribution", cfg.package)

    models_ns = importlib.import_module(f"{showcase_pkg}.models")

    def _resolve(name: str) -> type | None:
        ob = getattr(models_ns, name, None)
        return ob if isinstance(ob, type) else None

    return shape_context(
        inventory,
        obj=obj,
        site_name=str(site_name),
        auth=loaded.auth,
        has_pagination=bool(loaded.context.get("has_pagination")),
        resolve=_resolve,
        variant=cfg.docs.showcase_variant,
        examples=cfg.docs.examples,
        subpackage=sub,
    )
