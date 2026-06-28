from __future__ import annotations

from pydantic import BaseModel


class Status(BaseModel):
    """Alpha's Status — collides by NAME with beta.models.Status (DISTINCT fields).

    The model-name collision canary: federated registry-namespacing must keep this
    class separate from beta's same-named ``Status``.
    """

    code: int
    note: str


class PageInfo(BaseModel):
    """Alpha's PageInfo — collides by NAME with beta.models.PageInfo (DISTINCT
    fields). Reachable from the request body root (WidgetInput.page_info) so it
    enters the CLI model registry — the live cross-sub key collision B2 namespaces.
    """

    cursor: str | None = None


class WidgetInput(BaseModel):
    name: str
    size: int
    page_info: PageInfo | None = None


class Widget(BaseModel):
    id: str
    name: str
    status: Status | None = None


class WidgetList(BaseModel):
    """List envelope (mirrors the real SDK's List*200Response shape)."""

    page_info: PageInfo | None = None
    data: list[Widget] | None = None
