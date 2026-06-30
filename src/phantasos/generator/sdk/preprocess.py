"""Spec preprocessing — generic transforms + parameterized spec-specific helpers.

`clean(spec)` runs the generator-agnostic transforms every spec benefits from.
`hoist_items` / `tag_operations` are helpers a spec's `preprocess(spec)` hook calls
for its own quirks (these used to be hard-coded constants in preprocess_spec.py).
"""

from __future__ import annotations

import copy
import re
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


_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")


def normalize_operation_ids(
    spec: Any,
    *,
    strip_suffix: str | None = None,
    dots_to_underscore: bool = False,
    unify_separator: str | None = None,
    stats: dict[str, int] | None = None,
) -> None:
    """Rewrite every operation's ``operationId`` for OAG-friendly method names.

    Strips ``strip_suffix`` (e.g. ``.v2``), turns dots into ``unify_separator``
    (default ``_``) when ``dots_to_underscore``, and folds dashes into
    ``unify_separator`` — e.g. ``create.connector_group.v2`` ->
    ``create_connector_group``. Applied per-sub when
    ``SubPackage.normalize_operation_ids`` is set.
    """
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for method in _HTTP_METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict) or "operationId" not in op:
                continue
            oid = op["operationId"]
            if strip_suffix and oid.endswith(strip_suffix):
                oid = oid[: -len(strip_suffix)]
            if dots_to_underscore:
                oid = oid.replace(".", unify_separator or "_")
            if unify_separator:
                oid = oid.replace("-", unify_separator)
            op["operationId"] = oid
            if stats is not None:
                stats["operation_ids_normalized"] = (
                    stats.get("operation_ids_normalized", 0) + 1
                )


def fold_server_prefix(
    spec: Any, base_url: str, stats: dict[str, int] | None = None
) -> None:
    """Fold a spec's ``servers[]`` URL path-prefix into every operation path.

    Federated specs declare their per-domain prefix (e.g. ``/config/objects/v1``)
    in ``servers:`` rather than in the path keys, but the federated SDK shares ONE
    bare host (``base_url``) across all sub-packages — so that prefix is dropped and
    every call 404s. Pick the server whose host matches ``base_url`` and prepend its
    path to every ``paths`` key, then pin ``servers`` to the bare host, so the
    (host-overridden) runtime URL is ``base_url + <prefix><path>``. A spec that
    already carries its prefix in the path keys (bare or absent matching server) is
    a no-op.
    """
    from urllib.parse import urlsplit

    base_host = urlsplit(base_url).netloc
    prefix = ""
    for server in spec.get("servers") or []:
        url = server.get("url", "") if isinstance(server, dict) else ""
        parts = urlsplit(url)
        if parts.netloc == base_host:
            prefix = parts.path.rstrip("/")
            break
    if not prefix:
        return
    paths = spec.get("paths") or {}
    spec["paths"] = {f"{prefix}{p}": item for p, item in paths.items()}
    spec["servers"] = [{"url": base_url}]
    if stats is not None:
        stats["server_prefix_folded"] = stats.get("server_prefix_folded", 0) + len(
            paths
        )


def resolve_sub_host(spec: Any, base_url: str) -> str:
    """The host a federated sub should use.

    The shared ``base_url`` when the spec declares a server on that host (the common
    case — every sub on the one gateway); otherwise the sub's own server host. A few
    sub-packages live on a different gateway (e.g. ztna-connector serves from
    ``api.sase`` while the rest are ``api.strata``); the federation shares ONE
    Configuration, so the composer gives such a sub a host-overridden copy. Read the
    ORIGINAL ``servers`` (call before `fold_server_prefix`, which pins them).
    """
    from urllib.parse import urlsplit

    base_host = urlsplit(base_url).netloc
    fallback = ""
    for server in spec.get("servers") or []:
        url = server.get("url", "") if isinstance(server, dict) else ""
        parts = urlsplit(url)
        if parts.netloc == base_host:
            return base_url
        if parts.netloc and not fallback:
            fallback = f"{parts.scheme}://{parts.netloc}"
    return fallback or base_url


def spec_declares_header(spec: Any, header_name: str) -> bool:
    """True if the spec declares ``header_name`` as an ``in: header`` parameter.

    Drives spec-driven header scoping: the composer applies a `default_headers`
    entry only to sub-packages whose spec actually declares that header (as a
    component parameter or inline on an operation), so a header like
    ``x-panw-region`` rides only the subs that expect it — never objects/network,
    which never declared it. Case-insensitive (HTTP header names are).
    """
    target = header_name.lower()

    def _match(p: Any) -> bool:
        return (
            isinstance(p, dict)
            and str(p.get("in", "")).lower() == "header"
            and str(p.get("name", "")).lower() == target
        )

    component_params = (spec.get("components") or {}).get("parameters") or {}
    if any(_match(p) for p in component_params.values()):
        return True
    for path_item in (spec.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        groups = [path_item.get("parameters")]
        groups += [
            op.get("parameters")
            for m, op in path_item.items()
            if m in _HTTP_METHODS and isinstance(op, dict)
        ]
        for group in groups:
            if any(_match(p) for p in (group or [])):
                return True
    return False


_PLACEMENT = {"folder", "snippet", "device"}


def _leaf_props(node: Any) -> Any:
    """Yield ``(name, property_schema)`` for every leaf reachable through
    oneOf/anyOf (any depth).

    A leaf is a composition branch carrying ``properties`` — ALL of which are
    yielded (multi-field branches like nat-rules' destination-translation, which
    has ``required: []``, must not be reduced to their required fields), or a
    bare ``required``-only branch (yielded as plain strings).

    KNOWN LIMITATION: a ``{$ref, title}`` branch (the rare alternative form — e.g.
    ``dhcp`` on layer3-/vlan-interfaces) yields nothing. That field is not lifted;
    this is documented, not a silent drop.
    """
    for key in ("oneOf", "anyOf"):
        for b in node.get(key) or []:
            if not isinstance(b, dict):
                continue
            if "oneOf" in b or "anyOf" in b:
                yield from _leaf_props(b)
                continue
            props = b.get("properties") or {}
            if props:
                for n, sch in props.items():  # ALL props, not just `required`
                    yield n, sch
            else:
                for n in b.get("required") or []:  # required-only branch
                    yield n, {"type": "string"}


def flatten_scm_bodies(spec: Any, stats: dict[str, int] | None = None) -> None:
    """Lift oneOf/anyOf leaf properties back onto an SCM "configurable object".

    openapi-generator keeps only the composition when a schema has ``properties``
    + a sibling ``oneOf``/``anyOf``, discarding the payload. This re-merges every
    reachable leaf onto ``properties`` (merge-don't-clobber; lifted leaves stay
    optional) and removes the composition — but ONLY for schemas whose reachable
    leaf set contains a placement marker (``folder``/``snippet``/``device``), the
    universal SCM configurable-object signature. Real discriminated unions lacking
    that marker are left untouched (the corruption guard). Loops top-level
    ``components.schemas`` only.
    """
    schemas = (spec.get("components") or {}).get("schemas") or {}
    for s in schemas.values():
        if not isinstance(s, dict) or "properties" not in s:
            continue
        if "oneOf" not in s and "anyOf" not in s:
            continue
        leaves = dict(_leaf_props(s))
        if not (_PLACEMENT & set(leaves)):  # GUARD: only configurable SCM objects
            continue
        props = s["properties"]
        for n, sch in leaves.items():
            if n not in props:  # merge-don't-clobber
                props[n] = sch  # intentionally NOT added to `required`
        s.pop("oneOf", None)
        s.pop("anyOf", None)
        # The flattened type can no longer express "exactly one of ..." — carry the
        # human signal into the docstring. A value-type union flattened too (a
        # non-placement leaf is present) means there's also a value field to pick.
        note = (
            "Supply exactly one of folder/snippet/device (the configuration container)"
        )
        if set(leaves) - _PLACEMENT:
            note += ", and exactly one value field"
        note += "."
        existing = s.get("description")
        s["description"] = f"{existing}\n\n{note}" if existing else note
        if stats is not None:
            stats["flatten_scm_bodies"] = stats.get("flatten_scm_bodies", 0) + 1


def relax_readonly_required(spec: Any, stats: dict[str, int] | None = None) -> None:
    """Drop server-assigned (``readOnly``) fields from each schema's ``required``.

    SCM reuses one schema for create + response, so a ``readOnly`` field the server
    assigns (``id`` and friends — real set across the specs:
    ``{id, fqdn, group, log_type, name, oid}``) is faithfully ``required`` — which
    wrongly makes ``create()`` demand it. Dropping it from ``required`` (keeping the
    property) is safe: responses still type the field; create no longer demands a
    value the client cannot supply. Loops top-level ``components.schemas`` only and
    matches inline ``readOnly: true`` (the only form these specs use).
    """
    schemas = (spec.get("components") or {}).get("schemas") or {}
    for s in schemas.values():
        if not isinstance(s, dict):
            continue
        required = s.get("required")
        props = s.get("properties")
        if not isinstance(required, list) or not isinstance(props, dict):
            continue
        kept = [
            r
            for r in required
            if not (isinstance(props.get(r), dict) and props[r].get("readOnly") is True)
        ]
        dropped = len(required) - len(kept)
        if dropped:
            s["required"] = kept
            if stats is not None:
                stats["readonly_required_relaxed"] = (
                    stats.get("readonly_required_relaxed", 0) + dropped
                )


# Unicode general-category -> permissive Python-`re`-valid equivalent. `re`'s str
# patterns are already Unicode-aware (\d/\w/\s match Unicode), so these approximate
# the property classes well. Permissive ON PURPOSE: these patterns validate
# server-sent RESPONSE data, so the translation must never reject a value the server
# considered valid — over-matching (e.g. also accepting a symbol) is harmless.
_PROP_EQUIV = {
    # letters + marks -> any Unicode "letter-ish" word char (not digit/underscore)
    **dict.fromkeys(
        ["L", "Lu", "Ll", "Lt", "Lm", "Lo", "M", "Mn", "Mc", "Me"], r"[^\W\d_]"
    ),
    # numbers -> Unicode digit
    **dict.fromkeys(["N", "Nd", "Nl", "No"], r"\d"),
    # punctuation + symbols -> any non-word, non-space char
    **dict.fromkeys(
        ["P", "Pc", "Pd", "Ps", "Pe", "Pi", "Pf", "Po", "S", "Sm", "Sc", "Sk", "So"],
        r"[^\w\s]",
    ),
    # separators -> whitespace
    **dict.fromkeys(["Z", "Zs", "Zl", "Zp"], r"\s"),
}
_PROP_FALLBACK = r"[^\W\d_]"
_PROP_RE = re.compile(r"\\p\{([A-Za-z]+)\}")
_CLASS_RE = re.compile(r"\[((?:[^\]\\]|\\.)*)\]")


def _translate_class(body: str) -> str:
    """Turn a positive char-class body containing `\\p{}` into a `(?:...)` of
    Python-valid alternatives (the `\\p{}` tokens can't live inside `[...]`)."""
    props = _PROP_RE.findall(body)
    rest = _PROP_RE.sub("", body)  # the literal/simple-escape remainder
    alts = ([f"[{rest}]"] if rest else []) + [
        _PROP_EQUIV.get(p, _PROP_FALLBACK) for p in props
    ]
    return "(?:" + "|".join(dict.fromkeys(alts)) + ")"  # order-preserving dedup


def translate_unicode_property_regex(pattern: str) -> str:
    """Translate `\\p{X}` Unicode-property escapes to Python-`re`-valid regex.

    Python's `re` rejects `\\p{...}` (only the 3rd-party `regex` supports it), so an
    OAS `pattern:` such as ``^[\\p{L}\\p{N}\\p{P}\\s,.:_-]*$`` makes the generated
    pydantic validator raise ``PatternError`` at import/validation time. A positive
    character class containing `\\p{}` becomes a `(?:...)` alternation of equivalents
    (see ``_PROP_EQUIV``); any stray `\\p{}` outside a class is mapped standalone.
    Negated classes (`[^...]`) are left untouched (rare; restructuring would flip
    the meaning)."""
    if r"\p{" not in pattern:
        return pattern
    out = _CLASS_RE.sub(
        lambda m: (
            _translate_class(m.group(1))
            if (r"\p{" in m.group(1) and not m.group(1).startswith("^"))
            else m.group(0)
        ),
        pattern,
    )
    return _PROP_RE.sub(lambda m: _PROP_EQUIV.get(m.group(1), _PROP_FALLBACK), out)


def translate_property_patterns(spec: Any, stats: dict[str, int] | None = None) -> None:
    """Rewrite every `pattern:` in the spec that uses `\\p{}` so the generated SDK's
    `re.match(...)` compiles under Python's `re` (see
    ``translate_unicode_property_regex``). Walks the whole spec — patterns appear on
    any string schema, nested anywhere."""

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            p = node.get("pattern")
            if isinstance(p, str) and r"\p{" in p:
                new = translate_unicode_property_regex(p)
                if new != p:
                    node["pattern"] = new
                    if stats is not None:
                        stats["property_patterns_translated"] = (
                            stats.get("property_patterns_translated", 0) + 1
                        )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(spec)


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
