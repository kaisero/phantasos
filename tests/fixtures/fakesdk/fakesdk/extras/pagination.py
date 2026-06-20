"""Cursor pagination (hand-authored fixture; mirrors the real generated module)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

__all__ = ["paginate"]


def _next_cursor(page: Any) -> str | None:
    info = getattr(page, "page_info", None)
    if not info or not getattr(info, "has_next_page", False):
        return None
    cursor = getattr(info, "cursor", None)
    return cursor or None


def paginate(list_method: Callable[..., Any], **kwargs: Any) -> Iterator[Any]:
    """Yield every item across all pages of a list endpoint."""
    kwargs.pop("cursor", None)
    cursor: str | None = None
    while True:
        page = list_method(**({**kwargs, "cursor": cursor} if cursor else kwargs))
        yield from getattr(page, "data", None) or []
        cursor = _next_cursor(page)
        if cursor is None:
            return
