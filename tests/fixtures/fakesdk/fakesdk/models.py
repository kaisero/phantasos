from __future__ import annotations

from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel


class Color(str, Enum):
    RED = "red"
    BLUE = "blue"


class WidgetType(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"


class WidgetInput(BaseModel):
    name: str
    color: Optional[Color] = None
    tags: list[str] = []
    spec: Optional[dict] = None  # nested -> json flag


class SimpleGizmoInput(BaseModel):
    name: str


class ComplexGizmoInput(BaseModel):
    name: str
    depth: int


class CreateGizmoInput(BaseModel):
    """Undiscriminated oneOf wrapper, mirroring OAG output."""

    discriminator_value_class_map: dict = {}  # empty, like the real SDK
    actual_instance: Optional[Union[SimpleGizmoInput, ComplexGizmoInput]] = None
