from __future__ import annotations

import datetime
import enum

from pydantic import BaseModel, Field, StrictBool, StrictStr

from phantasos.generator.sdk.examples import synthesize_body


# A real str-enum (mirrors the generated SDK's LenientStrEnum, which is a
# `str, Enum`). Not a mock — exercises the synthesizer's real enum path.
# Deliberately (str, Enum) rather than StrEnum to match the generated code.
class Color(str, enum.Enum):  # noqa: UP042
    RED = "red"
    BLUE = "blue"


class UrlInput(BaseModel):
    url: StrictStr = Field(description="URL pattern")
    strict_mode: StrictBool | None = Field(default=False)  # optional -> omitted


class CustomApp(BaseModel):
    name: StrictStr = Field(description="Name")
    color: Color
    urls: list[UrlInput]
    created_at: datetime.datetime
    note: str | None = None  # optional -> omitted


def test_required_only_with_typed_placeholders() -> None:
    out = synthesize_body(CustomApp)
    assert out == (
        "CustomApp(\n"
        '    name="example",\n'
        '    color="red",\n'
        "    urls=[\n"
        "        UrlInput(\n"
        '            url="example",\n'
        "        ),\n"
        "    ],\n"
        '    created_at="2026-01-01T00:00:00Z",\n'
        ")"
    )
    assert "note" not in out and "strict_mode" not in out


# An int-valued enum (mirrors the generated SDK's int enums). Unlike a str-enum,
# the synthesizer must emit the value as a BARE literal (no surrounding quotes).
class Priority(int, enum.Enum):
    LOW = 1
    HIGH = 5


class ScalarFields(BaseModel):
    priority: Priority  # int-enum -> bare `1`
    ratio: float  # float scalar -> `0.0`
    count: int  # int scalar -> `0`
    enabled: StrictBool  # bool scalar -> `False`


def test_int_enum_and_float_scalars_render_bare() -> None:
    out = synthesize_body(ScalarFields)
    assert out == (
        "ScalarFields(\n"
        "    priority=1,\n"  # bare int-enum literal, not "1"
        "    ratio=0.0,\n"
        "    count=0,\n"
        "    enabled=False,\n"
        ")"
    )


class _Wrapper(BaseModel):
    actual_instance: CustomApp | UrlInput | None = None


def test_oneof_picks_named_variant() -> None:
    assert synthesize_body(_Wrapper, variant="UrlInput").startswith("UrlInput(")


def test_oneof_defaults_to_first_variant() -> None:
    assert synthesize_body(_Wrapper).startswith("CustomApp(")


def test_cycle_guard_terminates() -> None:
    # required self-reference would recurse forever without the guard
    class A(BaseModel):
        nxt: A  # required cycle

    A.model_rebuild()
    out = synthesize_body(A)
    assert out == "A(\n    nxt=A(...),\n)"
