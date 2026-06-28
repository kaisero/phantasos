from __future__ import annotations

from pydantic import BaseModel


class Status(BaseModel):
    """Beta's Status — same NAME as alpha.models.Status, DIFFERENT fields.

    The model-name collision canary: federated registry-namespacing must keep this
    class separate from alpha's same-named ``Status``.
    """

    state: str
    level: int


class GadgetInput(BaseModel):
    name: str
    watts: int


class Gadget(BaseModel):
    id: str
    name: str
    status: Status | None = None


class PageInfo(BaseModel):
    cursor: str | None = None


class GadgetList(BaseModel):
    """List envelope (mirrors the real SDK's List*200Response shape)."""

    page_info: PageInfo | None = None
    data: list[Gadget] | None = None
