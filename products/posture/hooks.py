"""posture spec-specific surgery (the vendor spec is read-only; transform here).

The vendor ships a non-standard top-level ``ExternalTags`` block (invalid OpenAPI
root field — fails OAG validation, like adem). We promote it to a standard root
``tags:`` array, rename the verbose ``Custom Posture Checks`` tag to ``Posture
Checks`` (so the SDK resource is ``client.posture_checks``), drop the original
block, and inject illustrative request-body examples for create/update.
"""

# Vendor tag -> the cleaner name we want OAG to group the resource under.
_TAG_RENAME = {"Custom Posture Checks": "Posture Checks"}

# Illustrative only: `data` is a free-form object (additionalProperties: true), so
# the real rule shape is vendor-defined. This is a plausible, clearly-illustrative
# expression — not a validated payload.
_EXAMPLE_VALUE = {
    "name": "Security Rule has logging enabled",
    "object_type": "security_rule",
    "severity": "High",
    "management_type": "cloud",
    "action": "alert",
    "data": {
        "operator": "and",
        "conditions": [{"field": "log-setting", "operator": "is-not-empty"}],
    },
}


def _rename(tag: str) -> str:
    return _TAG_RENAME.get(tag, tag)


def _promote_external_tags(spec):
    external = spec.pop("ExternalTags", None) or {}
    root_tags = []
    seen = set()
    for entry in external.values():
        if not isinstance(entry, dict):
            continue
        name = _rename(entry.get("title", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        tag = {"name": name}
        if entry.get("description"):
            tag["description"] = entry["description"]
        root_tags.append(tag)
    if root_tags:
        spec["tags"] = root_tags


def _rename_operation_tags(spec):
    for path_item in spec.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for op in path_item.values():
            if isinstance(op, dict) and isinstance(op.get("tags"), list):
                op["tags"] = [_rename(t) for t in op["tags"]]


_EXAMPLE_TARGETS = (("/posture/checks/v1", "post"), ("/posture/checks/v1/{id}", "put"))


def _inject_examples(spec):
    for path, method in _EXAMPLE_TARGETS:
        op = spec.get("paths", {}).get(path, {}).get(method)
        if not isinstance(op, dict):
            continue
        content = op.get("requestBody", {}).get("content", {}).get("application/json")
        if isinstance(content, dict):
            content.setdefault("examples", {})["typical"] = {
                "summary": "A custom posture check",
                "value": _EXAMPLE_VALUE,
            }


def _inject_security(spec):
    """The vendor spec declares NO securitySchemes/security, so OAG would generate
    methods that never send Authorization — every call 401s even with a valid token.
    Inject a global bearer requirement so the generated client attaches the SCM
    OAuth token supplied by phantasos's auth component.
    """
    comps = spec.setdefault("components", {})
    schemes = comps.setdefault("securitySchemes", {})
    schemes.setdefault(
        "BearerAuth", {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    )
    if not spec.get("security"):
        spec["security"] = [{"BearerAuth": []}]


def preprocess(spec):
    _promote_external_tags(spec)  # also drops the invalid ExternalTags root key
    _rename_operation_tags(spec)
    _inject_security(spec)
    _inject_examples(spec)
