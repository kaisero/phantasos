from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Union

from pydantic import BaseModel


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class WidgetType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


class WidgetInput(BaseModel):
    name: str
    priority: int                        # required int
    enabled: Optional[bool] = None       # optional bool
    color: Optional[Color] = None
    tags: list[str] = []
    spec: Optional[dict] = None  # nested -> json flag
    mode: Literal["fast", "slow"] = "fast"  # inline enum (Literal, not an Enum class)


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
