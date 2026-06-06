"""Cursor-pagination helper for the OpenAPI-Generator SDK.

List endpoints return a page object with `.data` (items) and `.page_info`
(`has_next_page`, `cursor`). The generated methods take a `cursor=` kwarg but don't
auto-page; `paginate` drives the loop and yields individual items.

Hand-maintained — copied into `prisma_browser/extras/` by the build.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

__all__ = ["paginate"]


def _next_cursor(page: Any) -> str | None:
    info = getattr(page, "page_info", None)
    if not info or not getattr(info, "has_next_page", False):
        return None
    cursor = getattr(info, "cursor", None)
    return cursor or None


def paginate(list_method: Callable[..., Any], **kwargs: Any) -> Iterator[Any]:
    """Yield every item across all pages of a list endpoint.

    `list_method` is a bound generated method, e.g. `UsersApi(client).list_users`.
    Filter kwargs (`limit`, `sort`, …) are forwarded; `cursor` is managed internally.

        from prisma_browser.api.users_api import UsersApi
        from prisma_browser.extras import paginate
        for user in paginate(UsersApi(api_client).list_users, limit=100):
            ...
    """
    kwargs.pop("cursor", None)
    cursor: str | None = None
    while True:
        page = list_method(**({**kwargs, "cursor": cursor} if cursor else kwargs))
        for item in getattr(page, "data", None) or []:
            yield item
        cursor = _next_cursor(page)
        if cursor is None:
            return
