"""Build the CLI docs render context from the resolved CliIR (IR-driven, generate-time).

No live CLI import and no mkdocstrings: the command reference is a pure function of
the CliIR. Shares flag grouping with the emitted CLI via flags.py so the reference
cannot drift from ``--help`` (D2). The SDK docs path (generator/sdk/docs.py) is NOT
reused (see docs/adr/0001-cli-docs-ir-driven-generate-time.md).
"""

from __future__ import annotations

from .cliconfig import CliDocsConfig
from .examples import render_invocation
from .flags import dedupe_flags, leaf, query_panel
from .ir import CliIR, Command, Flag

CONTEXT_KEYS = frozenset(
    {
        "cli_docs",
        "site_name",
        "distribution",
        "repo_url",
        "description",
        "objects",
        "showcase",
        "has_auth",
        "show_pagination_guide",
        "credentials",
        "error_envelope",
    }
)


def _usage(c: Command, distribution: str) -> str:
    parts = [distribution, c.verb, c.object]
    third = leaf(c)
    if third:
        parts.append(third)
    parts.append("[OPTIONS]")
    return " ".join(parts)


def _flag_row(f: Flag) -> dict[str, object]:
    return {
        "name": f.name,
        "type": f.py_type,
        "required": f.required,
        "choices": f.choices,
        "help": f.help,
    }


def _command_view(
    c: Command, *, distribution: str, override: str | None
) -> dict[str, object]:
    body, query = dedupe_flags(c)
    filters = [f for f in query if query_panel(f) == "Filters"]
    pagination = [f for f in query if query_panel(f) == "Pagination"]
    return {
        "key": c.key,
        "usage": _usage(c, distribution),
        "summary": c.summary,
        "description": c.description,
        "path_flags": [_flag_row(f) for f in c.path_params],
        "body_flags": [_flag_row(f) for f in body],
        "filter_flags": [_flag_row(f) for f in filters],
        "pagination_flags": [_flag_row(f) for f in pagination],
        "example": render_invocation(c, distribution=distribution, override=override),
        "columns": [{"header": col.header, "path": col.path} for col in c.columns],
    }


def _showcase(
    commands: list[Command], obj: str, variant: str | None
) -> dict[str, object]:
    verbs = {c.verb for c in commands if c.object == obj}
    return {
        "object": obj,
        # The oneOf create variant the Quickstart should showcase (D6); None when
        # the object's create is not a union or no variant was configured.
        "variant": variant,
        "has_create": "create" in verbs,
        "has_show": "show" in verbs,
        "has_update": "update" in verbs,
        "has_delete": "delete" in verbs,
    }


def build_cli_docs_context(
    ir: CliIR,
    docs: CliDocsConfig,
    *,
    distribution: str,
    site_name: str,
    repo_url: str | None = None,
    description: str = "",
) -> dict[str, object]:
    objects = sorted({c.object for c in ir.commands})
    if docs.showcase_object not in objects:
        raise ValueError(
            f"docs.showcase_object {docs.showcase_object!r} is not a CLI object; "
            f"available objects: {objects}"
        )
    if docs.showcase_variant is not None:
        # Fail loud like showcase_object (D6): a typo here would otherwise silently
        # drop the Quickstart's create example.
        variants = sorted(
            {
                c.variant
                for c in ir.commands
                if c.object == docs.showcase_object and c.variant
            }
        )
        if docs.showcase_variant not in variants:
            raise ValueError(
                f"docs.showcase_variant {docs.showcase_variant!r} is not a variant of "
                f"{docs.showcase_object!r}; available variants: {variants}"
            )
    grouped: list[dict[str, object]] = [
        {
            "object": obj,
            "commands": [
                _command_view(
                    c, distribution=distribution, override=docs.examples.get(c.key)
                )
                for c in ir.commands
                if c.object == obj
            ],
        }
        for obj in objects
    ]
    env = ir.error_envelope
    return {
        "cli_docs": True,
        "site_name": site_name,
        "distribution": distribution,
        "repo_url": repo_url,
        "description": description,
        "objects": grouped,
        "showcase": _showcase(ir.commands, docs.showcase_object, docs.showcase_variant),
        "has_auth": bool(ir.credential_fields),
        "show_pagination_guide": any(c.paginated for c in ir.commands),
        "credentials": [
            {
                "name": f.name,
                "env_var": f.env_var,
                "secret": f.secret,
                "required": f.required,
            }
            for f in ir.credential_fields
        ],
        "error_envelope": {
            "wrappers": list(env.wrappers),
            "error_field": env.error_field,
            "errors_field": env.errors_field,
            "message_field": env.message_field,
            "code_field": env.code_field,
            "fallback_keys": list(env.fallback_keys),
        },
    }
