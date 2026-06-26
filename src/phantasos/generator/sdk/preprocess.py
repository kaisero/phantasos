"""Spec preprocessing — generic transforms + parameterized spec-specific helpers.

`clean(spec)` runs the generator-agnostic transforms every spec benefits from.
`hoist_items` / `tag_operations` are helpers a spec's `preprocess(spec)` hook calls
for its own quirks (these used to be hard-coded constants in preprocess_spec.py).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

ANNOTATION_KEYS = {
    "description",
    "example",
    "examples",
    "title",
    "default",
    "deprecated",
    "readOnly",
    "writeOnly",
    "externalDocs",
}
STRUCTURAL_KEYS = {
    "$ref",
    "type",
    "properties",
    "items",
    "enum",
    "oneOf",
    "anyOf",
    "allOf",
}


def load(path: str) -> tuple[Any, Any]:
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=2, offset=0)
    with Path(path).open(encoding="utf-8") as f:
        return yaml.load(f), yaml


def dump(spec: Any, yaml: Any, path: str) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        yaml.dump(spec, f)


# ---- generic transforms ---------------------------------------------------------
def _is_ref(n: Any) -> bool:
    return isinstance(n, dict) and "$ref" in n


def _is_structural(n: Any) -> bool:
    return isinstance(n, dict) and bool(STRUCTURAL_KEYS & set(n.keys()))


def _resolve_type(schemas: Any, node: Any, seen: set[str] | None = None) -> str | None:
    if seen is None:
        seen = set()
    if not isinstance(node, dict):
        return None
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        if name in seen:
            return None
        seen.add(name)
        return _resolve_type(schemas, schemas.get(name, {}), seen)
    if "type" in node:
        return str(node["type"])
    if node.get("allOf"):
        for b in node["allOf"]:
            t = _resolve_type(schemas, b, seen)
            if t:
                return t
    if "properties" in node:
        return "object"
    return None


def collapse_allof(schemas: Any, node: Any, stats: dict[str, int]) -> None:
    """Collapse `allOf` whose single structural branch resolves to a non-object."""
    if isinstance(node, list):
        for i in node:
            collapse_allof(schemas, i, stats)
        return
    if not isinstance(node, dict):
        return
    if "allOf" in node and isinstance(node["allOf"], list):
        branches = node["allOf"]
        structural = [b for b in branches if _is_structural(b)]
        annotation = [
            b for b in branches if isinstance(b, dict) and set(b) <= ANNOTATION_KEYS
        ]
        if (
            len(structural) == 1
            and _is_ref(structural[0])
            and len(structural) + len(annotation) == len(branches)
        ):
            t = _resolve_type(schemas, structural[0])
            if t is not None and t != "object":
                ref = structural[0]["$ref"]
                node.clear()
                node["$ref"] = ref
                stats["allof_collapsed"] += 1
                return
    for v in node.values():
        collapse_allof(schemas, v, stats)


def _fix_mojibake(value: Any, stats: dict[str, int]) -> Any:
    if isinstance(value, str) and "Ã" in value:
        try:
            repaired = value.encode("latin-1").decode("utf-8")
            if repaired != value:
                stats["mojibake_fixed"] += 1
                return repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return value


def fix_strings_and_enums(node: Any, stats: dict[str, int]) -> None:
    """Repair mojibake strings and dedupe enum members (after repair)."""
    if isinstance(node, dict):
        for k in list(node.keys()):
            v = node[k]
            if k == "enum" and isinstance(v, list):
                seen: set[str] = set()
                out: list[Any] = []
                for item in v:
                    item2 = (
                        _fix_mojibake(item, stats) if isinstance(item, str) else item
                    )
                    key = item2 if isinstance(item2, str) else repr(item2)
                    if key in seen:
                        stats["enum_dups_removed"] += 1
                        continue
                    seen.add(key)
                    out.append(item2)
                node[k] = out
            elif isinstance(v, str):
                node[k] = _fix_mojibake(v, stats)
            else:
                fix_strings_and_enums(v, stats)
    elif isinstance(node, list):
        for i in node:
            fix_strings_and_enums(i, stats)


def strip_external_tags(spec: Any, stats: dict[str, int]) -> None:
    """Remove the non-standard top-level `ExternalTags` key (trips OAG validation)."""
    if "ExternalTags" in spec:
        del spec["ExternalTags"]
        stats["external_tags_stripped"] = stats.get("external_tags_stripped", 0) + 1


def clean(spec: Any, stats: dict[str, int]) -> None:
    """Run all generic, spec-agnostic transforms."""
    schemas = (spec.get("components") or {}).get("schemas")
    if schemas:
        collapse_allof(schemas, spec, stats)
    fix_strings_and_enums(spec, stats)
    strip_external_tags(spec, stats)


# ---- parameterized spec-specific helpers (called from a spec's preprocess hook) --
def hoist_items(
    spec: Any,
    hoists: list[tuple[str, str, str]],
    stats: dict[str, int] | None = None,
) -> None:
    """Hoist nested inline array-item objects into named components.

    `hoists`: list of (schema_name, property_name, new_component_name).
    """
    schemas = spec["components"]["schemas"]
    for control, prop, new_name in hoists:
        schema = schemas.get(control)
        if not schema:
            continue
        prop_schema = schema.get("properties", {}).get(prop)
        if not prop_schema or "items" not in prop_schema or new_name in schemas:
            continue
        schemas[new_name] = copy.deepcopy(prop_schema["items"])
        prop_schema["items"] = {"$ref": f"#/components/schemas/{new_name}"}
        if stats is not None:
            stats["items_hoisted"] = stats.get("items_hoisted", 0) + 1


def tag_operations(
    spec: Any,
    ops: list[tuple[str, str, str, str]],
    stats: dict[str, int] | None = None,
) -> None:
    """Add tags + operationId to operations that lack them.

    `ops`: list of (path, method, operation_id, tag).
    """
    for path, method, op_id, tag in ops:
        op = spec.get("paths", {}).get(path, {}).get(method)
        if not op:
            continue
        op.setdefault("operationId", op_id)
        if not op.get("tags"):
            op["tags"] = [tag]
        if stats is not None:
            stats["ops_tagged"] = stats.get("ops_tagged", 0) + 1
