"""prisma-browser spec-specific surgery (imperative; not expressible as hoist/tag)."""

# Component schemas whose generated class name would collide with a symbol OAG
# imports from pydantic into every model module. `ValidationError` is the live
# case: the oneOf module for PolicyBadRequestResponseError imports BOTH
# `pydantic.ValidationError` (used in its `except (ValidationError, ValueError)`
# clauses) and the model class, so the second import silently shadows the
# exception type -- ruff F811 + mypy `no attribute "from_json"`, and a runtime
# TypeError if it ever got that far. Rename the schema; the SDK exposes it as
# `ApiValidationError`.
SCHEMA_RENAMES = {"ValidationError": "ApiValidationError"}

# The vendor spec splits one resource across several tags (e.g. `Applications Read`
# / `Applications Actions`). OAG emits one *Api class per tag, and the facade
# wrapper rejects an object whose ops span api classes. Fold each split back into
# the one tag the object lived under, so `client.<object>` keeps one backing class.
_SPLIT_TAGS = {
    "Applications": ("Applications Read", "Applications Actions", "Applications Bulk"),
    "Plugins": ("Application Plugins",),
    "Devices": ("Devices Read", "Devices Actions"),
    "Users": ("Users Read", "Users Actions"),
    **{
        merged: tuple(f"{prefix} {part}" for part in ("Overview", "Positions", "Rules", "Sections"))
        for merged, prefix in (
            ("Access And Data Policy", "Access and Data"),
            ("Customization Policy", "Customization"),
            ("Security Policy", "Security"),
            ("Sign-In Policy", "Sign-In"),
        )
    },
}
TAG_MERGES = {split: merged for merged, splits in _SPLIT_TAGS.items() for split in splits}

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def preprocess(spec):
    _merge_tags(spec)
    schemas = spec.get("components", {}).get("schemas")
    if not schemas:
        return
    for old, new in SCHEMA_RENAMES.items():
        if old not in schemas:
            continue
        schemas[new] = schemas.pop(old)
    _rewrite_refs(spec)


def _merge_tags(spec):
    for item in spec.get("paths", {}).values():
        for method, op in item.items():
            if method in _HTTP_METHODS and op.get("tags"):
                op["tags"] = [TAG_MERGES.get(t, t) for t in op["tags"]]
    root, seen = [], set()
    for tag in spec.get("tags", []):
        name = TAG_MERGES.get(tag["name"], tag["name"])
        if name in seen:
            continue
        seen.add(name)
        root.append({**tag, "name": name} if name != tag["name"] else tag)
    if "tags" in spec:
        spec["tags"] = root


def _rewrite_refs(node):
    """Repoint every `$ref` (and discriminator mapping target) at the new name."""
    renamed = {f"#/components/schemas/{o}": f"#/components/schemas/{n}" for o, n in SCHEMA_RENAMES.items()}
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and value in renamed:
                node[key] = renamed[value]
            else:
                _rewrite_refs(value)
    elif isinstance(node, list):
        for item in node:
            _rewrite_refs(item)
