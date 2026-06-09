"""Deterministic classification of SDK methods into the CLI command tree.

Precedence (applied in build_cli_ir): cli.yml hide/skip > cli.yml override/request >
prefix heuristic. classify_name implements only the prefix heuristic + skip rules.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .ir import Verb

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
