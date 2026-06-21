"""Build the CLI docs render context from the resolved CliIR (IR-driven, generate-time).

No live CLI import and no mkdocstrings: the command reference is a pure function of
the CliIR. Shares flag grouping with the emitted CLI via flags.py so the reference
cannot drift from ``--help`` (D2). The SDK docs path (generator/sdk/docs.py) is NOT
reused (see docs/adr/0001-cli-docs-ir-driven-generate-time.md).
"""

from __future__ import annotations

import re

from .cliconfig import CliDocsConfig
from .examples import render_invocation
from .flags import dedupe_flags, leaf, query_panel
from .ir import CliIR, Command, Flag

# openapi-generator docstrings append a Sphinx block (:param:/:type:/:return:/...)
# after the prose. The per-parameter details are already rendered in the flag tables
# (from each Flag's `help`), so the block is pure redundancy + SDK-internal noise
# (_request_timeout/_headers/...). Drop everything from the first directive onward.
_SPHINX_BLOCK = re.compile(
    r"^[ \t]*:(?:param|type|return|rtype|raises)\b", re.MULTILINE
)

# The universal "Common" help-panel flags injected into EVERY emitted command at
# code-emit time (templates/_generated/commands.py.jinja). They are not in the CliIR,
# so they are listed statically here to keep the reference's flag surface complete
# (D9). `test_docs_common_flags_match_emitted` guards this set against the template so
# the two cannot drift. `--all` is intentionally absent — it sits in the Pagination
# panel, not Common.
_COMMON_FLAGS: list[dict[str, object]] = [
    {
        "name": "--output",
        "auth_only": False,
        "help": "Output format: json, yaml, or table.",
    },
    {
        "name": "--columns",
        "auth_only": False,
        "help": "Table columns as `HEADER=expr` pairs (implies --output table).",
    },
    {
        "name": "--dry-run",
        "auth_only": False,
        "help": "Print the HTTP request without sending it.",
    },
    {
        "name": "--verbose",
        "auth_only": False,
        "help": "Show full tracebacks for unexpected errors.",
    },
    {
        "name": "--quiet",
        "auth_only": False,
        "help": "Suppress everything below errors (also `-q`).",
    },
    {
        "name": "--pager",
        "auth_only": False,
        "help": "Page output taller than the terminal (`--no-pager` to disable).",
    },
    {
        "name": "--environment",
        "auth_only": True,
        "help": "Named environment to use for this command (also `-e`).",
    },
]

CONTEXT_KEYS = frozenset(
    {
        "site_name",
        "distribution",
        "repo_url",
        "description",
        "sdk_package",
        "env_prefix",
        "objects",
        "showcase",
        "has_auth",
        "show_pagination_guide",
        "credentials",
        "error_envelope",
        "common_flags",
    }
)


def _cell(text: str) -> str:
    """Escape a value for a GitHub-flavored-markdown table cell: a literal ``|`` would
    end the cell and a newline would break the row."""
    return text.replace("|", "\\|").replace("\n", " ").strip() if text else ""


def _usage(c: Command) -> str:
    """Lean reference heading: ``verb object [leaf]`` — no distribution prefix and no
    ``[OPTIONS]``. The flag tables document the options; the synthesized example shows
    the full runnable command."""
    parts = [c.verb, c.object]
    third = leaf(c)
    if third:
        parts.append(third)
    return " ".join(parts)


def _clean_description(text: str) -> str:
    """Keep only the human prose of a command description, dropping the trailing
    openapi-generator Sphinx block (see _SPHINX_BLOCK)."""
    if not text:
        return ""
    match = _SPHINX_BLOCK.search(text)
    return (text[: match.start()] if match else text).strip()


def _flag_row(f: Flag) -> dict[str, object]:
    return {
        "name": f.name,
        "type": f.py_type,
        "required": f.required,
        "choices": [_cell(c) for c in f.choices] if f.choices else None,
        "help": _cell(f.help),
    }


def _command_view(
    c: Command, *, distribution: str, override: str | None
) -> dict[str, object]:
    body, query = dedupe_flags(c)
    filters = [f for f in query if query_panel(f) == "Filters"]
    pagination = [f for f in query if query_panel(f) == "Pagination"]
    return {
        "key": c.key,
        "usage": _usage(c),
        "summary": c.summary,
        "description": _clean_description(c.description),
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
    }


def build_cli_docs_context(
    ir: CliIR,
    docs: CliDocsConfig,
    *,
    distribution: str,
    site_name: str,
    env_prefix: str = "",
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
        # Fail loud like showcase_object (D6). Validate against CREATE variants only:
        # the Quickstart shows the create example, so a variant that exists only on
        # (say) update would otherwise pass here yet silently drop the example.
        variants = sorted(
            {
                c.variant
                for c in ir.commands
                if c.object == docs.showcase_object and c.verb == "create" and c.variant
            }
        )
        if docs.showcase_variant not in variants:
            raise ValueError(
                f"docs.showcase_variant {docs.showcase_variant!r} is not a create "
                f"variant of {docs.showcase_object!r}; available: {variants}"
            )
    command_keys = {c.key for c in ir.commands}
    unknown_examples = sorted(set(docs.examples) - command_keys)
    if unknown_examples:
        # Fail loud (like the showcase fields): a typo'd example key would otherwise be
        # silently ignored, leaving the synthesized example in place.
        raise ValueError(
            f"docs.examples has keys matching no command: {unknown_examples}; "
            f"valid command keys: {sorted(command_keys)}"
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
    has_auth = bool(ir.credential_fields)
    env = ir.error_envelope
    return {
        "site_name": site_name,
        "distribution": distribution,
        "repo_url": repo_url,
        "description": description,
        "sdk_package": ir.sdk_package,
        "env_prefix": env_prefix,
        "objects": grouped,
        "showcase": _showcase(ir.commands, docs.showcase_object, docs.showcase_variant),
        "has_auth": has_auth,
        "show_pagination_guide": any(c.paginated for c in ir.commands),
        "common_flags": [f for f in _COMMON_FLAGS if has_auth or not f["auth_only"]],
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
