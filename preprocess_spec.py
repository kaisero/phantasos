#!/usr/bin/env python3
"""
Preprocess the Prisma Browser OpenAPI spec so that openapi-python-client can
generate a complete, correct SDK.

Addresses the review findings:
  1 (Critical) Missing 8 policy create/patch endpoints — caused by PostScope /
    PatchScope using `allOf` over array-typed refs ("Cannot take allOf a non-object").
    Fix: collapse annotation-only `allOf` wrappers whose single structural branch
    resolves to a non-object type, down to the bare $ref.
  2 (Critical) SecurityControls.from_dict crash — 4 control schemas dropped on a
    duplicate-model-name bug (nullable object + nested inline array-of-object).
    Fix: hoist the nested inline `items` objects into named top-level components.
  4 (partial — errors) Inconsistent 4xx/5xx handling — many error responses have no
    schema, so the generator returns None. Fix: attach the ApiError schema to every
    error response that lacks `content`.
  5 (Low/Med) Mojibake enum values + 4 untagged operations.
    Fix: repair mis-decoded UTF-8 strings (+ dedupe resulting enum members) and add
    tags/operationId to the User Requests operations.

Run:
  uv run --no-project --with ruamel.yaml --python 3.12 python preprocess_spec.py
"""
import copy
import sys
from ruamel.yaml import YAML

SRC = "prismaBrowserAPIspecWithSecurityPolicy.yaml"
DST = "prismaBrowserAPIspec.preprocessed.yaml"

ANNOTATION_KEYS = {
    "description", "example", "examples", "title", "default",
    "deprecated", "readOnly", "writeOnly", "externalDocs",
}
STRUCTURAL_KEYS = {"$ref", "type", "properties", "items", "enum", "oneOf", "anyOf", "allOf"}

yaml = YAML()
yaml.preserve_quotes = True
yaml.width = 4096  # avoid line-wrapping long descriptions
yaml.indent(mapping=2, sequence=2, offset=0)

stats = {
    "allof_collapsed": 0,
    "items_hoisted": 0,
    "errors_filled": 0,
    "mojibake_fixed": 0,
    "enum_dups_removed": 0,
    "ops_tagged": 0,
}


def is_ref(node):
    return isinstance(node, dict) and "$ref" in node


def is_structural(node):
    return isinstance(node, dict) and bool(STRUCTURAL_KEYS & set(node.keys()))


def ref_name(ref):
    return ref.rsplit("/", 1)[-1]


def resolve_effective_type(schemas, node, seen=None):
    """Best-effort resolution of a schema node's effective `type`."""
    if seen is None:
        seen = set()
    if not isinstance(node, dict):
        return None
    if "$ref" in node:
        name = ref_name(node["$ref"])
        if name in seen:
            return None
        seen.add(name)
        return resolve_effective_type(schemas, schemas.get(name, {}), seen)
    if "type" in node:
        return node["type"]
    if "allOf" in node and node["allOf"]:
        for branch in node["allOf"]:
            t = resolve_effective_type(schemas, branch, seen)
            if t:
                return t
    if "properties" in node:
        return "object"
    return None


# ---- Fix 1: collapse non-object allOf wrappers ----------------------------------
def collapse_allof(schemas, node):
    """Walk the whole tree; collapse `allOf` nodes whose single structural branch
    resolves to a non-object type (the generator cannot intersect non-objects)."""
    if isinstance(node, list):
        for item in node:
            collapse_allof(schemas, item)
        return
    if not isinstance(node, dict):
        return

    if "allOf" in node and isinstance(node["allOf"], list):
        branches = node["allOf"]
        structural = [b for b in branches if is_structural(b)]
        annotation_only = [
            b for b in branches
            if isinstance(b, dict) and set(b.keys()) <= ANNOTATION_KEYS
        ]
        if len(structural) == 1 and is_ref(structural[0]) and \
                len(structural) + len(annotation_only) == len(branches):
            t = resolve_effective_type(schemas, structural[0])
            if t is not None and t != "object":
                ref = structural[0]["$ref"]
                node.clear()
                node["$ref"] = ref
                stats["allof_collapsed"] += 1
                return  # nothing left to recurse into

    for v in node.values():
        collapse_allof(schemas, v)


# ---- Fix 2: hoist nested inline array-item objects into named components ----------
HOISTS = [
    ("AllowedOrBlockedExtensionsControl", "extensions", "AllowedOrBlockedExtensionEntry"),
    ("LaunchingExternalApplicationsControl", "exceptions", "ExternalApplicationLaunchException"),
    ("TrustedCertificateAuthoritiesControl", "additionalCertificates", "TrustedCertificateEntry"),
    ("InternetExplorerCompatibilityModeControl", "sites", "InternetExplorerCompatibilitySite"),
]


def hoist_items(schemas):
    for control, prop, new_name in HOISTS:
        schema = schemas.get(control)
        if not schema:
            print(f"  WARN: schema {control} not found; skipping hoist", file=sys.stderr)
            continue
        prop_schema = schema.get("properties", {}).get(prop)
        if not prop_schema or "items" not in prop_schema:
            print(f"  WARN: {control}.{prop}.items not found; skipping", file=sys.stderr)
            continue
        if new_name in schemas:
            print(f"  WARN: component {new_name} already exists; skipping", file=sys.stderr)
            continue
        schemas[new_name] = copy.deepcopy(prop_schema["items"])
        prop_schema["items"] = {"$ref": f"#/components/schemas/{new_name}"}
        stats["items_hoisted"] += 1


# ---- Fix 4 (errors): attach ApiError to error responses lacking content ----------
def fill_error_responses(spec):
    if "ApiError" not in spec.get("components", {}).get("schemas", {}):
        print("  WARN: ApiError schema missing; skipping error-response fill", file=sys.stderr)
        return
    api_error = {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            for status, resp in op.get("responses", {}).items():
                s = str(status)
                if (s.startswith("4") or s.startswith("5")) and isinstance(resp, dict):
                    if "content" not in resp:
                        resp["content"] = copy.deepcopy(api_error)
                        stats["errors_filled"] += 1


# ---- Fix 5a: repair mojibake strings + dedupe enums ------------------------------
def fix_mojibake(value):
    if isinstance(value, str) and "Ã" in value:  # 'Ã' — classic UTF-8-as-Latin-1
        try:
            repaired = value.encode("latin-1").decode("utf-8")
            if repaired != value:
                stats["mojibake_fixed"] += 1
                return repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return value


def walk_fix_strings(node):
    if isinstance(node, dict):
        for k in list(node.keys()):
            v = node[k]
            if k == "enum" and isinstance(v, list):
                fixed, seen, out = False, set(), []
                for item in v:
                    item2 = fix_mojibake(item) if isinstance(item, str) else item
                    key = item2 if isinstance(item2, str) else repr(item2)
                    if key in seen:
                        stats["enum_dups_removed"] += 1
                        continue
                    seen.add(key)
                    out.append(item2)
                node[k] = out
            elif isinstance(v, str):
                node[k] = fix_mojibake(v)
            else:
                walk_fix_strings(v)
    elif isinstance(node, list):
        for item in node:
            walk_fix_strings(item)


# ---- Fix 5b: tag + name the User Requests operations -----------------------------
USER_REQUEST_OPS = {
    ("/seb-api/v1/user-requests", "get"): "ListUserRequests",
    ("/seb-api/v1/user-requests/{id}", "get"): "GetUserRequestByID",
    ("/seb-api/v1/user-requests/{id}/action", "post"): "ActionUserRequest",
    ("/seb-api/v1/user-requests/{id}/revoke", "post"): "RevokeUserRequest",
}


def tag_user_requests(spec):
    for (path, method), op_id in USER_REQUEST_OPS.items():
        op = spec.get("paths", {}).get(path, {}).get(method)
        if not op:
            print(f"  WARN: {method.upper()} {path} not found; skipping tag", file=sys.stderr)
            continue
        op.setdefault("operationId", op_id)
        if "tags" not in op or not op["tags"]:
            op["tags"] = ["User Requests"]
        stats["ops_tagged"] += 1


def main():
    with open(SRC, encoding="utf-8") as f:
        spec = yaml.load(f)

    schemas = spec["components"]["schemas"]

    # Fix 1
    collapse_allof(schemas, spec)
    # Fix 2
    hoist_items(schemas)
    # Fix 4 (errors)
    fill_error_responses(spec)
    # Fix 5a
    walk_fix_strings(spec)
    # Fix 5b
    tag_user_requests(spec)

    with open(DST, "w", encoding="utf-8") as f:
        yaml.dump(spec, f)

    print("Preprocessing complete ->", DST)
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
