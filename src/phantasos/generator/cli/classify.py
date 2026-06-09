"""Deterministic classification of SDK methods into the CLI command tree.

Precedence (applied in build_cli_ir): cli.yml hide/skip > cli.yml override/request >
prefix heuristic. classify_name implements only the prefix heuristic + skip rules.
"""

from __future__ import annotations

from typing import cast

from pydantic import BaseModel, ConfigDict

from .cliconfig import CliConfig, VariantMap
from .inventory import FieldInfo, OperationInfo, OperationInventory, ParamInfo
from .ir import CliIR, Command, Flag, SubVerb, Verb

# (prefix, verb, sub_verb) — ORDER MATTERS: longer/compound prefixes first.
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("bulk_create_", "set", "bulk_create"),
    ("bulk_delete_", "del", "bulk_delete"),
    ("create_", "set", "create"),
    ("update_", "set", "update"),
    ("patch_", "set", "patch"),
    ("delete_", "del", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]

# Method-name fragments that mark non-CRUD ops to skip even if a verb prefix matches.
_SKIP_FRAGMENTS = ("_positions",)


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verb: Verb
    sub_verb: SubVerb
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
    for prefix, verb, sub_verb in _VERB_PREFIXES:
        if method.startswith(prefix):
            noun = _strip_id_suffix(method[len(prefix):])
            noun = _singularize(noun)
            return Classification(
                verb=verb, sub_verb=sub_verb, object=noun.replace("_", "-")
            )
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
    # TODO(phase2): not yet wired into build_cli_ir; reserved for
    # command-collision dedup.
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


def _id_flag(param: ParamInfo) -> Flag:
    return Flag(name="--id", param=param.name, py_type="str", kind="id",
                required=True, help=param.description)


def _query_flags(params: list[ParamInfo]) -> list[Flag]:
    return [
        Flag(name=_flag_name(p.name), param=p.name,
             # Enum query params stay permissive (str + choices), like fields_to_flags.
             py_type="str", kind="enum" if p.enum_values else "scalar",
             required=False, default=p.default, help=p.description,
             choices=p.enum_values)
        for p in params if p.location == "query"
    ]


def _body_flags_for(op: OperationInfo, model: str | None) -> list[Flag]:
    if model and model in op.body_fields:
        return fields_to_flags(op.body_fields[model])
    # single (non-union) body model
    for fields in op.body_fields.values():
        return fields_to_flags(fields)
    return []


def build_cli_ir(inv: OperationInventory, cfg: CliConfig) -> tuple[CliIR, list[str]]:
    commands: list[Command] = []
    unmapped: list[str] = []
    for op in inv.operations:
        key = f"{op.resource}.{op.method}"
        if key in cfg.hide:
            continue
        ov = cfg.override.get(key)
        cls = classify_name(op.method)
        if cls is None and key not in cfg.request:
            unmapped.append(key)
            continue
        if key in cfg.request:
            # request-namespace ops: handled in a later phase; skip silently
            continue
        if cls is None:
            continue  # unreachable: guarded above, satisfies type-narrowing
        verb: Verb = cast(Verb, ov.verb) if (ov and ov.verb) else cls.verb
        obj: str = ov.object if (ov and ov.object) else cls.object
        id_param = detect_id_param(op.params)
        path_flags = [_id_flag(id_param)] if id_param else []
        query_flags = _query_flags(op.params)
        variants = resolve_variants(op, cfg.variants.get(key))
        if variants:
            for v in variants:
                commands.append(Command(
                    verb=verb, object=obj, variant=v.name,
                    sdk_resource=op.resource, sdk_method=op.method,
                    path_params=path_flags, body_flags=_body_flags_for(op, v.model),
                    query_flags=query_flags, summary=op.summary,
                    description=op.description,
                    paginated=op.method.startswith("list_"),
                ))
        else:
            commands.append(Command(
                verb=verb, object=obj, variant=None,
                sdk_resource=op.resource, sdk_method=op.method,
                path_params=path_flags, body_flags=_body_flags_for(op, None),
                query_flags=query_flags, summary=op.summary, description=op.description,
                paginated=op.method.startswith("list_"),
            ))
    ir = CliIR(
        sdk_package=inv.sdk_package, sdk_version=inv.sdk_version, commands=commands
    )
    return ir, unmapped
