"""Cursor-pagination helpers for the Prisma Browser SDK.

The API paginates list endpoints with an opaque ``cursor`` plus a
``pageInfo`` object carrying ``hasNextPage``/``cursor``. The generated client
exposes this raw — callers must loop by hand. These helpers wrap the loop and
yield individual items across all pages, raising typed errors via ``unwrap``.

Hand-maintained — copied into ``prisma_browser_sdk/extras/`` by ``apply_overlay.py``.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Iterator

from ..types import UNSET
from .errors import unwrap

__all__ = ["paginate", "paginate_async"]


def _resolve(endpoint: Any, detailed_attr: str) -> Any:
    """Accept either an endpoint module or a ``*_detailed`` callable."""
    fn = getattr(endpoint, detailed_attr, None)
    if fn is not None:
        return fn
    if callable(endpoint):
        return endpoint
    raise TypeError(
        f"expected an endpoint module exposing {detailed_attr}() or a callable, "
        f"got {type(endpoint)!r}"
    )


def _next_cursor(page: Any) -> str | None:
    info = getattr(page, "page_info", None)
    if not info or not getattr(info, "has_next_page", False):
        return None
    cursor = getattr(info, "cursor", None)
    if cursor is None or cursor is UNSET:
        return None
    return cursor


def paginate(endpoint: Any, *, client: Any, **kwargs: Any) -> Iterator[Any]:
    """Yield every item across all pages of a list endpoint (sync).

    ``endpoint`` may be the endpoint module (e.g. ``api.users.list_users``) or
    its ``sync_detailed`` callable. Filter kwargs (``limit``, ``sort``, ...) are
    forwarded; ``cursor`` is managed internally.

        from prisma_browser_sdk.api.users import list_users
        from prisma_browser_sdk.extras import paginate

        for user in paginate(list_users, client=client, limit=100):
            ...
    """
    fn = _resolve(endpoint, "sync_detailed")
    kwargs.pop("cursor", None)
    cursor: str | None = None
    while True:
        call_kwargs = dict(kwargs)
        if cursor is not None:
            call_kwargs["cursor"] = cursor
        page = unwrap(fn(client=client, **call_kwargs))
        for item in getattr(page, "data", None) or []:
            yield item
        cursor = _next_cursor(page)
        if cursor is None:
            return


async def paginate_async(endpoint: Any, *, client: Any, **kwargs: Any) -> AsyncIterator[Any]:
    """Async counterpart of :func:`paginate`.

        async for user in paginate_async(list_users, client=client, limit=100):
            ...
    """
    fn = _resolve(endpoint, "asyncio_detailed")
    kwargs.pop("cursor", None)
    cursor: str | None = None
    while True:
        call_kwargs = dict(kwargs)
        if cursor is not None:
            call_kwargs["cursor"] = cursor
        page = unwrap(await fn(client=client, **call_kwargs))
        for item in getattr(page, "data", None) or []:
            yield item
        cursor = _next_cursor(page)
        if cursor is None:
            return
