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


class TargetA(BaseModel):
    """oneOf-variant A — exercises the inline-union variant_refs slug-qualification."""

    kind_a: str | None = None


class TargetB(BaseModel):
    """oneOf-variant B — distinct from TargetA (same collision-canary purpose for
    variant_refs as PageInfo is for a nested model_ref)."""

    kind_b: int | None = None


class WidgetInput(BaseModel):
    name: str
    size: int
    page_info: PageInfo | None = None
    # inline oneOf union field -> a ModelField with variant_refs (TargetA|TargetB),
    # so the merge's per-sub ref rewrite must slug-qualify the variants too.
    target: TargetA | TargetB | None = None


class Widget(BaseModel):
    id: str
    name: str
    status: Status | None = None


class WidgetList(BaseModel):
    """List envelope (mirrors the real SDK's List*200Response shape)."""

    page_info: PageInfo | None = None
    data: list[Widget] | None = None
