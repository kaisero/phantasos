"""Deterministic classification of SDK methods into the CLI command tree.

Precedence (applied in build_cli_ir): cli.yml hide/skip > cli.yml override/request >
prefix heuristic. classify_name implements only the prefix heuristic + skip rules.

Pure helpers (classify_name, detect_id_param, Classification, etc.) live in
generator.opmodel.classify and are re-exported here for backward compatibility.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict

from ..opmodel._pathutil import on_sys_path
from ..opmodel.classify import (
    _SKIP_FRAGMENTS,
    _VERB_PREFIXES,
    Classification,
    _singularize,
    _strip_id_suffix,
    detect_id_param,
)
from ..opmodel.classify import (
    classify_name as _opmodel_classify_name,
)
from ..opmodel.introspect import introspect
from .cliconfig import CliConfig, RequestMapping, VariantMap
from .columns import default_columns, resolve_columns
from .inventory import FieldInfo, OperationInfo, OperationInventory, ParamInfo
from .ir import (
    CliIR,
    ColumnSpec,
    Command,
    Flag,
    FlagKind,
    MethodBinding,
    ModelSchema,
    SubVerb,
    Verb,
)
from .modelschema import build_model_registry

__all__ = [
    "_SKIP_FRAGMENTS",
    "_VERB_PREFIXES",
    "Classification",
    "_singularize",
    "_strip_id_suffix",
    "build_cli_ir",
    "build_ir",
    "classify_name",
    "cli_operations",
    "detect_id_param",
    "fields_to_flags",
    "merge_federated_irs",
    "resolve_variants",
    "select_method_for_verb",
]

# (prefix, verb, sub_verb) — CLI-LOCAL classification prefixes. Mirrors the shared
# opmodel `_VERB_PREFIXES` but ADDS the PUT `update_` row. The shared map must NOT
# carry `update_` (the SDK wrapper needs `classify_name("update_*") -> None` so a
# PUT full-replace routes to `.replace`; see opmodel/classify.py + the contract
# tests in test_opmodel_classify.py). The CLI, however, needs `update_*` to surface
# a live `update` command (verb=update, sub_verb=put) — posture's ONLY update is a
# PUT with no PATCH twin, so without this its `update posture-check` command would
# vanish. This local map is the decouple point: SDK `.replace` AND CLI `update` both
# preserved.
_CLI_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("create_", "create", "create"),
    ("patch_", "update", "patch"),
    ("update_", "update", "put"),  # PUT full-replace; body stays required (see below)
    ("delete_", "delete", "delete"),
    ("get_", "show", "get"),
    ("list_", "show", "list"),
]


def classify_name(method: str) -> Classification | None:
    """CLI-local prefix classification: ADDS the PUT `update_*` -> (update, put) case.

    The shared `opmodel.classify_name` returns None for `update_*` (so the SDK
    wrapper routes PUTs to `.replace`). The CLI needs the `update` command, so this
    local variant classifies `update_*` first, then falls back to the shared helper
    for every other prefix. Importing modules (the SDK wrapper, contract tests) keep
    using `opmodel.classify_name` directly; only `cli.classify` (and its consumers /
    `test_cli_classify.py`) see the PUT case.
    """
    if any(frag in method for frag in _SKIP_FRAGMENTS):
        return None
    for prefix, verb, sub_verb in _CLI_VERB_PREFIXES:
        if method.startswith(prefix):
            noun = _strip_id_suffix(method[len(prefix) :])
            noun = _singularize(noun)
            return Classification(
                verb=verb, sub_verb=sub_verb, object=noun.replace("_", "-")
            )
    return _opmodel_classify_name(method)


def cli_operations(
    package: str, sdk_path: Path, *, registry_attr: str = "_WRAPPERS"
) -> OperationInventory:
    """Inventory built from the SDK's typed wrappers (`_WRAPPERS`/`_bindings`).

    The CLI's command tree is still classified off the RAW operation names, so
    cli.yml keeps resolving by the UNCHANGED `api_resource.raw_method` key. This
    walks the facade's `_WRAPPERS` (object attr -> (wrapper class, backing `*Api`
    attr)) and, for every binding in each wrapper's `_bindings` (clean verb ->
    list of `{raw_method, requires, body, ...}`), emits one `OperationInfo` keyed
    `resource=api_resource`, `method=raw_method` — reusing the raw-method
    introspection verbatim (identical params/body_fields/response columns) and
    stamping the wrapper-rebase routing fields onto it:

    - `object_attr` — the `client.<object>` dispatch target (Command.sdk_resource).
    - `clean_method` — the typed wrapper verb (MethodBinding.sdk_method).
    - `has_body` — whether the binding carries a request body, so build_cli_ir
      sends it under the wrapper method's `body` kwarg.

    The raw `(api_resource, raw_method)` set covered by `_bindings` is exactly the
    set the legacy `_RESOURCES` introspection enumerates (one binding per raw op),
    so the projected command tree is unchanged — only dispatch is re-pointed at
    the wrappers.
    """
    inv = introspect(package, sdk_path, registry_attr="_RESOURCES")
    by_raw: dict[tuple[str, str], OperationInfo] = {
        (op.resource, op.method): op for op in inv.operations
    }

    with on_sys_path(sdk_path):
        facade = importlib.import_module(f"{package}.extras.facade")
        wrappers: dict[str, tuple[type[Any], str]] = getattr(facade, registry_attr)

    operations: list[OperationInfo] = []
    for obj_attr, (wrapper_cls, api_attr) in wrappers.items():
        bindings: dict[str, list[dict[str, Any]]] = wrapper_cls._bindings
        for clean_method, blist in bindings.items():
            for b in blist:
                raw_method = b["raw_method"]
                base = by_raw.get((api_attr, raw_method))
                if base is None:
                    # A binding with no matching raw-`*Api` introspection record
                    # (no public method / excluded suffix). Skip — there is no
                    # operation surface for the CLI to mount.
                    continue
                operations.append(
                    base.model_copy(
                        update={
                            "object_attr": obj_attr,
                            "clean_method": clean_method,
                            "has_body": b.get("body") is not None,
                        }
                    )
                )

    return OperationInventory(
        sdk_package=inv.sdk_package,
        sdk_version=inv.sdk_version,
        operations=operations,
    )


def select_method_for_verb(methods: list[str]) -> str:
    """Return the preferred method when multiple share the same verb.

    Prefer the shortest name (fewest path params); ties broken alphabetically.
    """
    # TODO(phase2): not yet wired into build_cli_ir; reserved for
    # command-collision dedup.
    return sorted(methods, key=lambda m: (m.count("_"), m))[0]


def _flag_name(param: str) -> str:
    return "--" + param.replace("_", "-")


def fields_to_flags(
    fields: list[FieldInfo], schema: ModelSchema | None = None
) -> list[Flag]:
    # When a ModelSchema is supplied (the deepened path), stamp each json body
    # flag's model_ref by FIELD NAME (FieldInfo.name == ModelField.name; both are
    # python field names, NOT aliases). Without a schema (models=None) every
    # model_ref stays None — backward-compatible with the un-deepened path.
    refmap = {mf.name: mf for mf in schema.fields} if schema else {}
    flags: list[Flag] = []
    for f in fields:
        # Enum flags stay permissive: emit str + completer choices, never a
        # validating Enum (the SDK uses LenientStrEnum — unknowns must pass through).
        # Scalar fields use their normalized scalar_type (int/bool/float/str) so
        # that Typer performs type validation at the CLI layer (Task 3).
        # json/id kinds keep str.
        if f.kind == "enum":
            py_type = "str"
        elif f.kind == "scalar":
            py_type = f.scalar_type
        else:
            py_type = "str"
        mf = refmap.get(f.name)
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
                model_ref=(mf.model_ref if mf else None),
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


def _query_flags(
    params: list[ParamInfo], defaults: dict[str, Any] | None = None
) -> list[Flag]:
    defaults = defaults or {}
    return [
        Flag(
            name=_flag_name(p.name),
            param=p.name,
            # Enum query params stay permissive (str + choices), like fields_to_flags.
            # Plain int/bool scalars get their real type for _coerce to work correctly.
            py_type="str" if p.enum_values else p.scalar_type,
            kind="enum" if p.enum_values else "scalar",
            required=False,
            default=p.default,
            help=p.description,
            choices=p.enum_values,
            cli_default=defaults.get(p.name),
        )
        for p in params
        if p.location == "query"
    ]


def _body_flags_for(
    op: OperationInfo, model: str | None, models: dict[str, ModelSchema] | None
) -> list[Flag]:
    reg = models or {}
    if model and model in op.body_fields:
        return fields_to_flags(op.body_fields[model], reg.get(model))
    # single (non-union) body model
    for name, fields in op.body_fields.items():
        return fields_to_flags(fields, reg.get(name))
    return []


def _path_flags(params: list[ParamInfo], id_param: ParamInfo | None) -> list[Flag]:
    """Every required path param becomes a flag: the detected id as kind 'id'
    named --id; other required path params (discriminators like `type`) as
    enum/scalar flags."""
    flags: list[Flag] = []
    for p in params:
        if p.location != "path":
            continue
        if id_param is not None and p.name == id_param.name:
            flags.append(
                Flag(
                    name="--id",
                    param=p.name,
                    py_type="str",
                    kind="id",
                    required=False,
                    help=p.description,
                )
            )
        else:
            kind: FlagKind = "enum" if p.enum_values else "scalar"
            # Enums stay permissive (str + choices); plain int/bool scalars get typed.
            py_type = "str" if p.enum_values else p.scalar_type
            flags.append(
                Flag(
                    name=_flag_name(p.name),
                    param=p.name,
                    py_type=py_type,
                    kind=kind,
                    required=False,
                    help=p.description,
                    choices=p.enum_values,
                )
            )
    return flags


def _required_path_names(params: list[ParamInfo]) -> list[str]:
    return [p.name for p in params if p.location == "path"]


def _body_param_info(op: OperationInfo) -> ParamInfo | None:
    """Return the first body ParamInfo for the operation, or None."""
    for p in op.params:
        if p.location == "body":
            return p
    return None


def _dispatch_body_param(op: OperationInfo, body_info: ParamInfo | None) -> str | None:
    """The runtime kwarg carrying the request body for THIS op's dispatch target.

    Wrapper-backed ops (cli_operations) dispatch through `client.<object>.<verb>`,
    whose body parameter is always named `body` — so the body is sent under
    `"body"` regardless of the raw `*Api` body-param name. On the raw-`*Api` path
    the body keeps its raw parameter name. Returns None when the op has no body.
    """
    if op.clean_method is not None:
        return "body" if op.has_body else None
    return body_info.name if body_info else None


def _command_key(verb: str, obj: str, variant: str | None) -> str:
    return f"{verb}:{obj}" + (f":{variant}" if variant else "")


def _merge_flags(target: list[Flag], extra: list[Flag]) -> None:
    seen = {f.name for f in target}
    for f in extra:
        if f.name not in seen:
            target.append(f)
            seen.add(f.name)


def _emit_request(
    groups: dict[str, Command],
    op: OperationInfo,
    mapping: RequestMapping,
    defaults: dict[str, Any] | None = None,
    models: dict[str, ModelSchema] | None = None,
) -> None:
    key = _command_key("request", mapping.object, mapping.action)
    id_param = detect_id_param(op.params)
    body_info = _body_param_info(op)
    body_model = body_info.body_model if body_info else None
    binding = MethodBinding(
        # Dispatch through the typed wrapper verb when the op was discovered via
        # `_WRAPPERS` (cli_operations); else the raw method name (raw-`*Api` path).
        sdk_method=op.clean_method or op.method,
        sub_verb="action",
        requires=_required_path_names(op.params),
        body_param=_dispatch_body_param(op, body_info),
        body_model=body_model,
        body_wrapper=None,
    )
    cmd = groups.get(key)
    if cmd is None:
        cmd = Command(
            verb="request",
            object=mapping.object,
            action=mapping.action,
            variant=None,
            variant_param=None,
            key=key,
            sdk_resource=op.object_attr or op.resource,
            path_params=_path_flags(op.params, id_param),
            body_flags=_body_flags_for(op, body_model, models),
            query_flags=_query_flags(op.params, defaults),
            summary=op.summary,
            description=op.description,
            paginated=False,
        )
        groups[key] = cmd
    else:
        _merge_flags(cmd.path_params, _path_flags(op.params, id_param))
        _merge_flags(cmd.body_flags, _body_flags_for(op, body_model, models))
        _merge_flags(cmd.query_flags, _query_flags(op.params, defaults))
    cmd.bindings.append(binding)


def _validate_defaults(cfg: CliConfig, ops_index: dict[str, OperationInfo]) -> None:
    """Validate cli.yml `defaults` op keys + param names up front.

    Build fails on a typo (unknown operation / non-query param) rather than
    silently ignoring it. Keyed by the UNCHANGED raw `api_resource.raw_method`.
    """
    for op_key, params_map in cfg.defaults.items():
        op_info = ops_index.get(op_key)
        if op_info is None:
            raise ValueError(f"cli.yml defaults: unknown operation {op_key!r}")
        query_names = {p.name for p in op_info.params if p.location == "query"}
        unknown = set(params_map) - query_names
        if unknown:
            raise ValueError(
                f"cli.yml defaults.{op_key}: {', '.join(sorted(unknown))}"
                f" is not a query param (available:"
                f" {', '.join(sorted(query_names)) or 'none'})"
            )


def _emit_command(
    groups: dict[str, Command],
    op: OperationInfo,
    *,
    verb: Verb,
    obj: str,
    variant: str | None,
    sub_verb: SubVerb,
    body_model: str | None,
    cfg: CliConfig,
    models: dict[str, ModelSchema] | None,
    variant_param: str | None = None,
) -> None:
    """Build (or merge into) the Command for a classified operation.

    Promoted from the `_emit` closure of `build_cli_ir`; `groups`/`cfg`/`models`
    (formerly captured) are now explicit params.
    """
    key = _command_key(verb, obj, variant)
    id_param = detect_id_param(op.params)
    body_info = _body_param_info(op)
    bp_model: str | None
    bp_wrapper: str | None
    if body_model:  # variant command: build the variant, wrap in the param's model
        bp_model = body_model
        bp_wrapper = (
            body_info.body_model
            if body_info and body_info.body_model != body_model
            else None
        )
    elif body_info:  # plain body: build the param's model directly
        bp_model = body_info.body_model
        bp_wrapper = None
    else:
        bp_model = None
        bp_wrapper = None
    binding = MethodBinding(
        # Wrapper verb for `_WRAPPERS`-discovered ops; raw method otherwise.
        sdk_method=op.clean_method or op.method,
        sub_verb=sub_verb,
        requires=_required_path_names(op.params),
        body_param=_dispatch_body_param(op, body_info),
        body_model=bp_model,
        body_wrapper=bp_wrapper,
    )
    op_defaults = cfg.defaults.get(f"{op.resource}.{op.method}")
    cmd = groups.get(key)
    if cmd is None:
        cmd = Command(
            verb=verb,
            object=obj,
            variant=variant,
            variant_param=variant_param,
            key=key,
            sdk_resource=op.object_attr or op.resource,
            path_params=_path_flags(op.params, id_param),
            body_flags=_body_flags_for(op, body_model, models),
            query_flags=_query_flags(op.params, op_defaults),
            summary=op.summary,
            description=op.description,
            paginated=(sub_verb == "list"),
        )
        groups[key] = cmd
    else:
        cmd.paginated = cmd.paginated or sub_verb == "list"
        _merge_flags(cmd.path_params, _path_flags(op.params, id_param))
        _merge_flags(cmd.body_flags, _body_flags_for(op, body_model, models))
        _merge_flags(cmd.query_flags, _query_flags(op.params, op_defaults))
    cmd.bindings.append(binding)
    # --id is semantically required for update and delete: the operation targets
    # a specific resource by id.  show intentionally keeps it optional (list
    # without --id is valid).  create has no id path param.
    if verb in ("update", "delete"):
        for f in cmd.path_params:
            if f.kind == "id":
                f.required = True


def _relax_patch_body_requiredness(groups: dict[str, Command]) -> None:
    """Relax body-field requiredness for update commands that include a PATCH.

    Per-command, post-merge: order-independent. PATCH is partial → no body field
    should be mandatory. A PUT-only update is a full replace → the model's
    required fields STAY required (omitting one would wipe it server-side). A
    command that merges BOTH (a `patch_` + an `update_` PUT on one object) is
    relaxed because PATCH offers a valid partial update. Deciding from the final
    binding set (not per-binding in `_emit_command`) avoids the emit-order
    sensitivity a per-binding gate would have.
    """
    for cmd in groups.values():
        if cmd.verb == "update" and any(b.sub_verb == "patch" for b in cmd.bindings):
            for f in cmd.body_flags:
                f.required = False


def _flag_get_by_id_only(groups: dict[str, Command]) -> None:
    """Flag `show` commands that can only fetch a single object by id.

    A `show` with a single get-by-id binding and NO list operation can only
    fetch one object by id; flag it so the runtime emits a precise "no list
    operation" diagnostic instead of the generic no-match message. The strict
    `requires == [id]` check keeps the flag (and message) accurate: a show whose
    get also needs a discriminator (e.g. by_type_and_id) is NOT flagged.
    """
    for cmd in groups.values():
        id_flag = next((f for f in cmd.path_params if f.kind == "id"), None)
        cmd.get_by_id_only = (
            cmd.verb == "show"
            and id_flag is not None
            and bool(cmd.bindings)  # else all() below is vacuously true on no bindings
            and not any(b.sub_verb == "list" for b in cmd.bindings)
            and all(b.requires == [id_flag.param] for b in cmd.bindings)
        )


def _resolve_columns(
    groups: dict[str, Command],
    cfg: CliConfig,
    dispatch_index: dict[str, OperationInfo],
) -> None:
    """Resolve table columns + items_field per OBJECT (never per command).

    CRITICAL: columns resolve per OBJECT, never per command. Real-SDK write ops
    return DIVERGENT response models (e.g. create_device_group ->
    CreateDeviceGroup201Response{device_group_id} — not the DeviceGroup item),
    so validating cli.yml columns against each command's own response model
    would fail the build on valid configs. The object's canonical row shape is
    its show command's item model (list envelope unwrapped, else get's model);
    the resolved columns attach to every command of the object (a jmespath
    miss renders as an empty cell). items_field stays per-command.
    """
    rank = {"list": 0, "get": 1}

    def _rep_op(cmd: Command) -> OperationInfo | None:
        for b in sorted(cmd.bindings, key=lambda b: rank.get(b.sub_verb, 9)):
            op = dispatch_index.get(f"{cmd.sdk_resource}.{b.sdk_method}")
            if op is not None and op.response_fields:
                return op
        return None

    obj_fields: dict[str, list[FieldInfo]] = {}
    for cmd in groups.values():  # the show command defines the object's rows
        if cmd.verb == "show" and (rep := _rep_op(cmd)) is not None:
            obj_fields[cmd.object] = rep.response_fields
    for cmd in groups.values():  # objects without a show command: any response model
        if cmd.object not in obj_fields and (rep := _rep_op(cmd)) is not None:
            obj_fields[cmd.object] = rep.response_fields

    objects = {c.object for c in groups.values()}
    unknown_objects = set(cfg.columns) - objects
    if unknown_objects:
        raise ValueError(
            "cli.yml columns: unknown object(s): " + ", ".join(sorted(unknown_objects))
        )
    resolved: dict[str, list[ColumnSpec]] = {}
    for obj in objects:
        entries = cfg.columns.get(obj)
        fields = obj_fields.get(obj)
        if entries is not None:
            # curated: validate against the object's row shape (syntax-only
            # when no response model was introspectable)
            resolved[obj] = resolve_columns(entries, fields or [], obj)
        elif fields:
            resolved[obj] = default_columns(fields)
    for cmd in groups.values():
        cmd.columns = resolved.get(cmd.object, [])
        if (rep := _rep_op(cmd)) is not None:
            cmd.items_field = rep.items_field


def build_cli_ir(
    inv: OperationInventory,
    cfg: CliConfig,
    *,
    models: dict[str, ModelSchema] | None = None,
) -> tuple[CliIR, list[str]]:
    groups: dict[str, Command] = {}
    unmapped: list[str] = []

    # cli.yml defaults: validate op keys and param names up front (build fails
    # on a typo rather than silently ignoring it). Keyed by the UNCHANGED raw
    # `api_resource.raw_method` (cli.yml keys + classification key off this).
    ops_index = {f"{op.resource}.{op.method}": op for op in inv.operations}
    # Column resolution looks an op up by a command's DISPATCH key
    # (`sdk_resource.sdk_method`) — the object attr + clean verb on the wrapper
    # path, the api attr + raw method otherwise. Several raw ops can collapse onto
    # one wrapper verb (e.g. get-by-id + get-by-type-and-id -> `get`); first record
    # carrying response fields wins, matching the raw-path lookup.
    dispatch_index: dict[str, OperationInfo] = {}
    for op in inv.operations:
        dkey = f"{op.object_attr or op.resource}.{op.clean_method or op.method}"
        if op.response_fields or dkey not in dispatch_index:
            dispatch_index[dkey] = op
    _validate_defaults(cfg, ops_index)

    for op in inv.operations:
        key0 = f"{op.resource}.{op.method}"
        if key0 in cfg.hide:
            continue
        if key0 in cfg.request:
            _emit_request(groups, op, cfg.request[key0], cfg.defaults.get(key0), models)
            continue
        ov = cfg.override.get(key0)
        cls = classify_name(op.method)
        if cls is None:
            unmapped.append(key0)
            continue
        verb = cast(Verb, ov.verb) if ov and ov.verb else cls.verb
        obj = ov.object if ov and ov.object else cls.object
        vmap = cfg.variants.get(key0)
        variants = resolve_variants(op, vmap)
        if variants:
            for v in variants:
                _emit_command(
                    groups,
                    op,
                    verb=verb,
                    obj=obj,
                    variant=v.name,
                    sub_verb=cls.sub_verb,
                    body_model=v.model,
                    cfg=cfg,
                    models=models,
                    variant_param=vmap.path_param if vmap else None,
                )
        else:
            _emit_command(
                groups,
                op,
                verb=verb,
                obj=obj,
                variant=None,
                sub_verb=cls.sub_verb,
                body_model=None,
                cfg=cfg,
                models=models,
            )

    _relax_patch_body_requiredness(groups)
    _flag_get_by_id_only(groups)
    _resolve_columns(groups, cfg, dispatch_index)

    ir = CliIR(
        sdk_package=inv.sdk_package,
        sdk_version=inv.sdk_version,
        facade_module=f"{inv.sdk_package}.extras.facade",
        commands=list(groups.values()),
        models=models or {},
    )
    return ir, unmapped


def _qualify_sub_refs(slug: str, ir_sub: CliIR) -> None:
    """Slug-qualify every registry POINTER in one sub's IR, in place.

    A sub's registry is self-contained (no cross-sub refs), so every bare
    `model_ref`/`variant_ref` resolves to a model in THIS sub — prefix each with
    `f"{slug}."` to match the qualified keys the merge stores. Done before merging
    so flags/fields and the registry keys move together.
    """
    q = f"{slug}."
    for schema in ir_sub.models.values():
        for mf in schema.fields:
            if mf.model_ref:
                mf.model_ref = q + mf.model_ref
            if mf.variant_refs:
                mf.variant_refs = [q + v for v in mf.variant_refs]
    for cmd in ir_sub.commands:
        for flag in (*cmd.path_params, *cmd.body_flags, *cmd.query_flags):
            if flag.model_ref:
                flag.model_ref = q + flag.model_ref


def merge_federated_irs(
    package: str,
    sdk_version: str,
    subs: list[tuple[str, CliIR, list[str]]],
) -> tuple[CliIR, list[str]]:
    """Merge per-sub CliIRs into ONE federated CliIR.

    Each sub's commands are stamped with its snake slug (`Command.subpackage`) and
    concatenated; unmapped ops are slug-prefixed for clarity; models are merged under
    SLUG-QUALIFIED keys (`f"{slug}.{ClassName}"`) so two subs defining a same-named
    model (e.g. both expose a `PageInfo`) stay distinct instead of last-sub-wins.
    Each sub's registry refs (`Flag.model_ref`, `ModelField.model_ref` /
    `variant_refs`) are rewritten to the qualified key in lockstep, so key and ref
    stay consistent and `synth_skeleton`/docs/`--help` resolve to the RIGHT sub's
    model. Single-spec builds run no merge and keep bare keys (`build_cli_ir`).
    `facade_module` points at the top-level package, which exposes the COMPOSING
    `Client` (not a sub-facade); the runtime navigates `client.<slug>.<object>`.

    S1 (cross-sub object-uniqueness): two subs defining the same `Command.object`
    raise a clear build error naming the object + both subs. Objects are globally
    unique across prisma-access today; this guards a future regression.
    """
    commands: list[Command] = []
    unmapped: list[str] = []
    models: dict[str, ModelSchema] = {}
    object_owner: dict[str, str] = {}
    for slug, ir_sub, unmapped_sub in subs:
        _qualify_sub_refs(slug, ir_sub)
        for cmd in ir_sub.commands:
            owner = object_owner.get(cmd.object)
            if owner is not None and owner != slug:
                raise ValueError(
                    f"federated build: object {cmd.object!r} is defined by both "
                    f"sub-packages {owner!r} and {slug!r}; objects must be unique "
                    "across sub-packages"
                )
            object_owner[cmd.object] = slug
            cmd.subpackage = slug
            commands.append(cmd)
        unmapped.extend(f"{slug}.{u}" for u in unmapped_sub)
        models.update({f"{slug}.{name}": s for name, s in ir_sub.models.items()})
    ir = CliIR(
        sdk_package=package,
        sdk_version=sdk_version,
        facade_module=package,  # the composing Client lives on the top-level package
        commands=commands,
        models=models,
    )
    return ir, unmapped


def build_ir(package: str, sdk_path: Path, cfg: CliConfig) -> tuple[CliIR, list[str]]:
    """Build the CliIR for a single- OR federated-spec SDK.

    A federated distribution exposes `_SUBPACKAGES` (snake slug -> sub-facade
    `Client`) on its top-level package (detected exactly as the SDK-docs
    `gen_ref_pages` does). Each sub is introspected/classified independently and
    merged into one CliIR via `merge_federated_irs`. A single-spec SDK (no
    `_SUBPACKAGES`) keeps the unchanged single-pass path.

    `cfg` drives the single-spec build. For a federated build, `cfg.subpackages`
    is the ENROLLMENT ALLOWLIST: a non-empty map builds ONLY its listed subs
    (∩ `_SUBPACKAGES`); an empty/absent map enrolls ALL subs (backward-compatible
    config-less build). Each enrolled sub gets its own `cli.yml` delta from
    `cfg.subpackages[slug]` (an empty `CliConfig` if its value is `{}`). A sub
    listed but absent from `_SUBPACKAGES` is a typo → hard error. FAIL-LOUD
    (federated only): after merging, any non-CRUD op left
    unmapped (no `request:`/`hide:` in its sub's section) is a HARD build error,
    so a command is never silently dropped on drift. The single-spec path keeps
    today's behavior — it returns `unmapped` for cli.py to print as a stderr note.
    """
    with on_sys_path(sdk_path):
        top = importlib.import_module(package)
        subpkgs = getattr(top, "_SUBPACKAGES", None)
        version = getattr(top, "__version__", "0.0.0")
    if not subpkgs:
        inv = cli_operations(package, sdk_path)
        models = build_model_registry(package, sdk_path, inv)
        return build_cli_ir(inv, cfg, models=models)
    # ENROLLMENT ALLOWLIST: a non-empty `subpackages:` map lists exactly the subs
    # to build (∩ `_SUBPACKAGES`, in `_SUBPACKAGES` order) — a sub not listed is
    # skipped, so the federated CLI can ship a thin slice without mapping the rest
    # of the SDK's non-CRUD ops. An empty/absent map enrolls ALL subs (config-less
    # federated build stays backward-compatible). A listed sub absent from
    # `_SUBPACKAGES` is a typo → fail loud.
    if cfg.subpackages:
        unknown = set(cfg.subpackages) - set(subpkgs)
        if unknown:
            raise ValueError(
                "federated cli.yml subpackages: enrolled sub(s) "
                + ", ".join(sorted(unknown))
                + " not in the SDK's _SUBPACKAGES ("
                + ", ".join(subpkgs)
                + ")"
            )
        enrolled = [slug for slug in subpkgs if slug in cfg.subpackages]
    else:
        enrolled = list(subpkgs)
    subs: list[tuple[str, CliIR, list[str]]] = []
    for slug in enrolled:
        sub_pkg = f"{package}.{slug}"
        inv = cli_operations(sub_pkg, sdk_path)
        models = build_model_registry(sub_pkg, sdk_path, inv)
        sub_cfg = cfg.subpackages.get(slug, CliConfig())
        ir_sub, unmapped_sub = build_cli_ir(inv, sub_cfg, models=models)
        subs.append((slug, ir_sub, unmapped_sub))
    ir, unmapped = merge_federated_irs(package, version, subs)
    if unmapped:
        raise ValueError(
            "federated build: non-CRUD op(s) with no cli.yml mapping: "
            + ", ".join(sorted(unmapped))
            + " — add a `subpackages.<slug>.request` (or `.hide`) entry"
        )
    return ir, unmapped
