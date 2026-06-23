"""Shared flag-grouping helpers for the CLI generator.

Both the emitted command modules (render_cli) and the docs command reference
(docs.py) import these so the reference's flag set and grouping can never drift
from the emitted ``--help`` (design D2). NOT shared with the SDK generator path.
"""

from __future__ import annotations

from .ir import Command, Flag

# Pagination/sort query params get their own help panel; everything else is a filter.
PAGINATION_PARAMS = frozenset(
    {
        "limit",
        "offset",
        "cursor",
        "page",
        "page_size",
        "per_page",
        "sort",
        "order",
        "sort_by",
        "order_by",
        "sort_order",
    }
)


def query_panel(f: Flag) -> str:
    return "Pagination" if f.param in PAGINATION_PARAMS else "Filters"


def leaf(c: Command) -> str | None:
    """The third command segment: a oneOf variant OR a request action (mutually
    exclusive)."""
    return c.variant or c.action


def dedupe_flags(c: Command) -> tuple[list[Flag], list[Flag]]:
    """Return (body, query) flags deduped against path params (path wins), then
    query deduped against body — exactly the flag set the emitted command exposes."""
    path_names = {f.param for f in c.path_params}
    body = [f for f in c.body_flags if f.param not in path_names]
    body_names = {f.param for f in body}
    query = [
        f
        for f in c.query_flags
        if f.param not in path_names and f.param not in body_names
    ]
    return body, query
