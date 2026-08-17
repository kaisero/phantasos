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


def preprocess(spec):
    schemas = spec.get("components", {}).get("schemas")
    if not schemas:
        return
    for old, new in SCHEMA_RENAMES.items():
        if old not in schemas:
            continue
        schemas[new] = schemas.pop(old)
    _rewrite_refs(spec)


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
