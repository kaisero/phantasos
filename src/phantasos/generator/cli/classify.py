"""Deterministic classification of SDK methods into the CLI command tree.

Precedence (applied in build_cli_ir): cli.yml hide/skip > cli.yml override/request >
prefix heuristic. classify_name implements only the prefix heuristic + skip rules.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .cliconfig import VariantMap
from .inventory import FieldInfo, OperationInfo, ParamInfo
from .ir import Flag, Verb

# (prefix, verb) — ORDER MATTERS: longer/compound prefixes first.
_VERB_PREFIXES: list[tuple[str, Verb]] = [
    ("bulk_create_", "set"),
    ("bulk_delete_", "del"),
    ("create_", "set"),
    ("update_", "set"),
    ("patch_", "set"),
    ("delete_", "del"),
    ("get_", "show"),
    ("list_", "show"),
]

# Method-name fragments that mark non-CRUD ops to skip even if a verb prefix matches.
_SKIP_FRAGMENTS = ("_positions",)


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verb: Verb
    object: str  # kebab-case noun


def _strip_id_suffix(noun: str) -> str:
    for suffix in ("_by_type_and_id", "_by_id", "_by_type"):
        if noun.endswith(suffix):
            return noun[: -len(suffix)]
    return noun


def _singularize(noun: str) -> str:
    if noun.endswith("ies"):
        return noun[:-3] + "y"
    if noun.endswith("ses"):
        return noun[:-2]
    if noun.endswith("s") and not noun.endswith("ss"):
        return noun[:-1]
    return noun


def classify_name(method: str) -> Classification | None:
    """Prefix-heuristic classification. Returns None for unmapped/skip ops."""
    if any(frag in method for frag in _SKIP_FRAGMENTS):
        return None
    for prefix, verb in _VERB_PREFIXES:
        if method.startswith(prefix):
            noun = _strip_id_suffix(method[len(prefix) :])
            noun = _singularize(noun)
            return Classification(verb=verb, object=noun.replace("_", "-"))
    return None


def detect_id_param(params: list[ParamInfo]) -> ParamInfo | None:
    """The id is the single required path param that is not a discriminator enum.

    Works before SDK id-name harmonization lands (handles id, device_group_id, etc.).
    """
    candidates = [p for p in params if p.location == "path" and not p.enum_values]
    if not candidates:
        return None
    # Prefer an exactly-named "id"; else the first non-enum path param.
    for p in candidates:
        if p.name == "id":
            return p
    return candidates[0]


def select_method_for_verb(methods: list[str]) -> str:
    """Return the preferred method when multiple share the same verb.

    Prefer the shortest name (fewest path params); ties broken alphabetically.
    """
    return sorted(methods, key=lambda m: (m.count("_"), m))[0]


def _flag_name(param: str) -> str:
    return "--" + param.replace("_", "-")


def fields_to_flags(fields: list[FieldInfo]) -> list[Flag]:
    flags: list[Flag] = []
    for f in fields:
        # Enum flags stay permissive: emit str + completer choices, never a
        # validating Enum (the SDK uses LenientStrEnum — unknowns must pass through).
        py_type = "str" if f.kind == "enum" else f.annotation
        flags.append(
            Flag(
                name=_flag_name(f.name),
                param=f.name,
                py_type=py_type,
                kind=f.kind,
                required=f.required,
                default=f.default,
                help=f.description,
                choices=f.enum_values,
            )
        )
    return flags


class ResolvedVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    name: str  # path-enum value, e.g. "custom"
    model: str  # variant model class name, e.g. "CustomApplicationInput"


def resolve_variants(
    op: OperationInfo, vmap: VariantMap | None
) -> list[ResolvedVariant]:
    """Map a method's path-enum values to variant models via cli.yml (the SDK oneOf
    wrapper is undiscriminated, so this mapping must be authored)."""
    if vmap is None:
        return []
    return [
        ResolvedVariant(name=value, model=model) for value, model in vmap.map.items()
    ]
