from __future__ import annotations

from pydantic import BaseModel


class Status(BaseModel):
    """Alpha's Status — collides by NAME with beta.models.Status (DISTINCT fields).

    The model-name collision canary: federated registry-namespacing must keep this
    class separate from beta's same-named ``Status``.
    """

    code: int
    note: str


class WidgetInput(BaseModel):
    name: str
    size: int


class Widget(BaseModel):
    id: str
    name: str
    status: Status | None = None


class PageInfo(BaseModel):
    cursor: str | None = None


class WidgetList(BaseModel):
    """List envelope (mirrors the real SDK's List*200Response shape)."""

    page_info: PageInfo | None = None
    data: list[Widget] | None = None
