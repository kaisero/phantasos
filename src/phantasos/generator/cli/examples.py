"""Synthesize illustrative CLI invocations from the resolved command IR.

Deliberately NOT shared with generator/sdk/examples.py: the SDK path synthesizes
Python constructor expressions; this path renders shell invocations. Keeping the
value strategy duplicated keeps the two generator paths independently evolvable
(see docs/adr/0001-cli-docs-ir-driven-generate-time.md). It DOES share intra-CLI
helpers from flags.py.
"""

from __future__ import annotations

from .flags import dedupe_flags, leaf
from .ir import Command, Flag, ModelSchema

# Honest placeholder values rendered as shell tokens. Required-only examples stay
# short and copy-pasteable; full flag detail lives in the reference flag tables.
_SCALARS: dict[str, str] = {
    "int": "0",
    "float": "0.0",
    "bool": "true",
    "str": '"example"',
}


def example_value(flag: Flag, models: dict[str, ModelSchema] | None = None) -> str:
    """A shell-safe example value token for one flag.

    A json flag carrying a known body model (``model_ref``) renders the real
    minimal skeleton (required-only) from the registry, single-quoted for the
    shell; an anonymous json flag (no ``model_ref``) or an empty registry falls
    back to ``'{}'``.
    """
    if flag.choices:
        return flag.choices[0]
    if flag.kind == "json":
        if flag.model_ref and models:
            import json as _json

            from .ir import synth_skeleton

            skel = synth_skeleton(models, flag.model_ref, full=False)
            return "'" + _json.dumps(skel, separators=(",", ":")) + "'"
        return "'{}'"
    if flag.kind == "file":
        return "./file"
    if flag.kind == "id":
        return '"example"'
    return _SCALARS.get(flag.py_type, '"example"')


def _required_flags(c: Command) -> list[Flag]:
    """Required flags the command exposes, in path → body → query order.

    Built on flags.dedupe_flags so the synthesized example can't drift from the
    reference table / ``--help`` (one source of truth for the flag set)."""
    body, query = dedupe_flags(c)
    return [f for f in (*c.path_params, *body, *query) if f.required]


def render_invocation(
    command: Command,
    *,
    distribution: str,
    override: str | None = None,
    models: dict[str, ModelSchema] | None = None,
) -> str:
    """A one-line invocation example (required flags only) or the verbatim override."""
    if override is not None:
        return override.strip()
    parts = [distribution, command.verb, command.object]
    third = leaf(command)
    if third:
        parts.append(third)
    for f in _required_flags(command):
        parts.append(f"{f.name} {example_value(f, models)}")
    return " ".join(parts)
