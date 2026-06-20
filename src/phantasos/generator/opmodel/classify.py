"""Pure classification helpers for SDK methods.

These helpers are shared between the CLI generator and any other generator that
needs to classify SDK method names into CRUD verbs and object nouns. CLI-specific
logic (build_cli_ir and friends) lives in generator.cli.classify.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..cli.ir import SubVerb, Verb
from .inventory import ParamInfo

# (prefix, verb, sub_verb) — ORDER MATTERS: longer/compound prefixes first.
_VERB_PREFIXES: list[tuple[str, Verb, SubVerb]] = [
    ("create_", "create", "create"),
    ("patch_", "update", "patch"),
    ("delete_", "delete", "delete"),
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
            noun = _strip_id_suffix(method[len(prefix) :])
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


def OBJECT_OF(method: str) -> str | None:  # noqa: N802
    """Object noun (kebab) for a CRUD-prefixed raw method, else None.

    ONLY handles classifiable (verb-prefixed) methods. For None-classified ops the
    object is NOT reliably derivable from the method alone (the verb phrase may be
    1+ tokens: `suspend`, `bulk_create`, `publish_draft`), so those are mapped to an
    existing CRUD object on the same api class in build_wrapper_context (Task 3.1),
    or fail the build demanding an sdk.yml operations entry. Never guess here.
    """
    for prefix, _, _ in _VERB_PREFIXES:
        if method.startswith(prefix):
            return _singularize(_strip_id_suffix(method[len(prefix) :])).replace(
                "_", "-"
            )
    return None
