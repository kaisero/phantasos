from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel


class LenientStrEnum(str, Enum):
    """Mirrors the real SDK's LenientStrEnum: unknown string values pass through."""

    @classmethod
    def _missing_(cls, value: object) -> LenientStrEnum | None:
        if isinstance(value, str):
            pseudo = str.__new__(cls, value)
            pseudo._name_ = value
            pseudo._value_ = value
            return pseudo
        return None


class Color(LenientStrEnum):
    RED = "red"
    BLUE = "blue"


class WidgetType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


class Tag(BaseModel):
    label: str


class EmailTarget(BaseModel):
    email: str


class PhoneTarget(BaseModel):
    phone: str


class Contact(BaseModel):
    """How to reach the widget owner."""

    name: str  # required
    timezone: Optional[str] = None


class Node(BaseModel):  # self-referential cycle
    label: str
    child: Optional[Node] = None


class WidgetProfile(BaseModel):  # all-optional → exercises non-empty guarantee
    contact: Optional[Contact] = None
    tags: list[Tag] = []
    target: Optional[Union[EmailTarget, PhoneTarget]] = None
    graph: Optional[Node] = None


class WidgetInput(BaseModel):
    name: str
    priority: int  # required int
    enabled: Optional[bool] = None  # optional bool
    color: Optional[Color] = None
    tags: list[str] = []
    spec: Optional[dict] = None  # nested -> json flag
    mode: Literal["fast", "slow"] = "fast"  # inline enum (Literal, not an Enum class)
    profile: Optional[WidgetProfile] = None  # nested model -> json flag with model_ref


class SimpleGizmoInput(BaseModel):
    name: str


class ComplexGizmoInput(BaseModel):
    name: str
    depth: int


class CreateGizmoInput(BaseModel):
    """Undiscriminated oneOf wrapper, mirroring OAG output."""

    discriminator_value_class_map: dict = {}  # empty, like the real SDK
    actual_instance: Optional[Union[SimpleGizmoInput, ComplexGizmoInput]] = None

    def __init__(self, *args: object, **kwargs: object) -> None:
        if args:
            super().__init__(actual_instance=args[0])
        else:
            super().__init__(**kwargs)


class Widget(BaseModel):
    """Response item model (what get returns; what the list envelope contains)."""

    id: str
    name: str
    color: Optional[Color] = None
    priority: int = 0
    enabled: Optional[bool] = None
    tags: list[str] = []
    spec: Optional[dict] = None  # nested -> excluded from default columns
    members: list[dict] = []  # list-of-objects -> joined preview


class PageInfo(BaseModel):
    cursor: Optional[str] = None


class WidgetList(BaseModel):
    """List envelope, mirroring the real SDK's List*200Response shape."""

    page_info: Optional[PageInfo] = None
    data: Optional[list[Widget]] = None


class CreateWidget201Response(BaseModel):
    """Divergent create response, mirroring the real SDK (e.g.
    CreateDeviceGroup201Response carries only the new id — NOT the item shape).
    Forces the columns pipeline to resolve per OBJECT (against the show item
    model), never per command."""

    widget_id: str


Node.model_rebuild()  # resolve the forward-ref self-cycle (Node.child)
