from __future__ import annotations

from pydantic import BaseModel


class Status(BaseModel):
    """Beta's Status — same NAME as alpha.models.Status, DIFFERENT fields.

    The model-name collision canary: federated registry-namespacing must keep this
    class separate from alpha's same-named ``Status``.
    """

    state: str
    level: int


class PageInfo(BaseModel):
    """Beta's PageInfo — same NAME as alpha.models.PageInfo, DIFFERENT field.
    Reachable from the request body root (GadgetInput.page_info) so it enters the
    CLI model registry — the live cross-sub key collision B2 namespaces.
    """

    total: int | None = None


class GadgetInput(BaseModel):
    name: str
    watts: int
    page_info: PageInfo | None = None


class Gadget(BaseModel):
    id: str
    name: str
    status: Status | None = None


class GadgetList(BaseModel):
    """List envelope (mirrors the real SDK's List*200Response shape)."""

    page_info: PageInfo | None = None
    data: list[Gadget] | None = None
