"""Scoped introspect + verb classification + docs context for generated SDKs."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from ...productconfig import DocsOperations, LoadedProduct
    from ..cli.inventory import OperationInfo, OperationInventory

# Leading method token -> CRUD slot. "patch"/"put" also mean update.
_VERB_SLOT = {
    "create": "create",
    "get": "read",
    "list": "list",
    "update": "update",
    "patch": "update",
    "put": "update",
    "delete": "delete",
}
_BY_SUFFIX = re.compile(r"_by_.*$")


def _slot(method: str) -> str | None:
    return _VERB_SLOT.get(method.split("_", 1)[0])


def _noun(method: str) -> str:
    """Method minus its verb prefix and any `_by_<...>` suffix."""
    rest = method.split("_", 1)[1] if "_" in method else ""
    return _BY_SUFFIX.sub("", rest)


def _matches_resource(resource: str, noun: str) -> bool:
    r, n = resource.rstrip("s"), noun.rstrip("s")
    return r == n or resource == noun or resource.startswith(noun)


def _required_path_count(op: OperationInfo) -> int:
    return sum(1 for p in op.params if p.location == "path" and p.required)


def classify_operations(
    operations: list[OperationInfo], resource: str, overrides: DocsOperations | None
) -> dict[str, OperationInfo]:
    """Map each CRUD slot to its canonical OperationInfo (present slots only)."""
    by_method = {op.method: op for op in operations}
    override_map = {k: v for k, v in vars(overrides).items() if v} if overrides else {}

    slots: dict[str, OperationInfo] = {}
    for slot in ("create", "read", "list", "update", "delete"):
        pinned = override_map.get(slot)
        if pinned:
            if pinned not in by_method:
                raise ValueError(
                    f"docs.operations.{slot} = {pinned!r} is not a method of "
                    f"resource {resource!r}; available: {sorted(by_method)}"
                )
            slots[slot] = by_method[pinned]
            continue
        candidates = [
            op
            for op in operations
            if _slot(op.method) == slot
            and not op.method.startswith("bulk_")
            and _matches_resource(resource, _noun(op.method))
        ]
        if candidates:
            slots[slot] = min(
                candidates, key=lambda op: (_required_path_count(op), len(op.method))
            )
    return slots


def _op_dict(op: OperationInfo) -> dict[str, object]:
    required_args: list[dict[str, object]] = []
    for p in op.params:
        if not p.required:
            continue
        if p.location == "body":
            required_args.append(
                {
                    "name": p.name,
                    "kind": "body",
                    "body_model": p.body_model,
                }
            )
        elif p.location == "path":
            placeholder = p.enum_values[0] if p.enum_values else f"<{p.name}>"
            required_args.append(
                {
                    "name": p.name,
                    "kind": "path",
                    "placeholder": str(placeholder),
                }
            )
    return {
        "method": op.method,
        "summary": op.summary,
        "description": op.description,
        "required_args": required_args,
        "return_model": op.return_model,
        "items_field": op.items_field,
    }


def shape_context(
    inventory: OperationInventory,
    *,
    resource: str,
    site_name: str,
    auth: object | None,
    overrides: DocsOperations | None,
    has_pagination: bool,
) -> dict[str, object]:
    ops = [op for op in inventory.operations if op.resource == resource]
    slots = classify_operations(ops, resource, overrides)
    operations = {slot: _op_dict(op) for slot, op in slots.items()}
    showcase = {
        "attr": resource,
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


def _validate_resource(inventory: OperationInventory, resource: str) -> None:
    available = sorted({op.resource for op in inventory.operations})
    if resource not in available:
        raise ValueError(
            f"docs.showcase_resource {resource!r} not found; "
            f"available resources: {available}"
        )


def build_docs_context(loaded: LoadedProduct, project_dir: Path) -> dict[str, object]:
    """Scoped introspect of the showcase resource -> docs context dict."""
    from ..cli.introspect import introspect

    cfg = loaded.config
    if cfg.docs is None:  # guarded by the caller; this is a defensive check
        raise AssertionError("build_docs_context called without a docs config")
    inventory = introspect(cfg.package, project_dir)
    _validate_resource(inventory, cfg.docs.showcase_resource)
    site_name = cfg.docs.site_name or loaded.context.get("distribution", cfg.package)
    return shape_context(
        inventory,
        resource=cfg.docs.showcase_resource,
        site_name=str(site_name),
        auth=loaded.auth,
        overrides=cfg.docs.operations,
        has_pagination=bool(loaded.context.get("has_pagination")),
    )
