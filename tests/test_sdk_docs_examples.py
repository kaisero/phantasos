from __future__ import annotations

import datetime
import enum
from typing import Any

from pydantic import BaseModel, Field, StrictBool, StrictStr

from phantasos.generator.sdk.examples import (
    assemble_reference_docstring,
    reference_example,
    synthesize_body,
)


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


# OAG oneOf shape: one `oneof_schema_N_validator` field per branch + a runtime
# `actual_instance` (the variant-resolution signal is the validator fields).
class _Wrapper(BaseModel):
    oneof_schema_1_validator: CustomApp | None = None
    oneof_schema_2_validator: UrlInput | None = None
    actual_instance: Any = None


def test_oneof_picks_named_variant() -> None:
    # WRAP form: the named variant is nested inside its wrapper (C2).
    assert synthesize_body(_Wrapper, variant="UrlInput").startswith(
        "_Wrapper(UrlInput("
    )


def test_oneof_defaults_to_first_variant() -> None:
    assert synthesize_body(_Wrapper).startswith("_Wrapper(CustomApp(")


# ---------------------------------------------------------------------------
# Task C: a wrapper BODY must synthesize a FULL-nested, constructable payload
# variant — `AddressGroups(GroupType(Static(...)))` — not an opaque placeholder.
# These mirror the real OAG anyOf/oneOf shape WITHOUT importing prisma_access
# (gate-resident; prisma-access is built only under `nox -s sdk-docs`). The real
# constructability proof lives in tests/test_sdk_docs_wrapper_rendering.py.
# A wrapper carries `<any|one>of_schema_N_validator` fields + `actual_instance:
# Any` (anyOf emits `Any` at runtime — the Union is TYPE_CHECKING-only).


class _Static(BaseModel):  # payload leaf
    static: list[StrictStr]
    additional_properties: dict[str, Any] = {}


class _Folder(BaseModel):  # SCM container leaf (single {folder} field)
    folder: StrictStr
    additional_properties: dict[str, Any] = {}


class _Snippet(BaseModel):  # SCM container leaf (single {snippet} field)
    snippet: StrictStr
    additional_properties: dict[str, Any] = {}


class _GroupType(BaseModel):  # payload sub-wrapper (oneOf of leaves)
    oneof_schema_1_validator: _Static | None = None
    actual_instance: Any = None


class _ContainerType(BaseModel):  # SCM container branch (folder/snippet leaves)
    oneof_schema_1_validator: _Folder | None = None
    oneof_schema_2_validator: _Snippet | None = None
    actual_instance: Any = None


class _AddressGroups(BaseModel):  # top anyOf: a payload branch + a container branch
    anyof_schema_1_validator: _GroupType | None = None
    anyof_schema_2_validator: _ContainerType | None = None
    actual_instance: Any = None


def test_synthesize_body_picks_payload_variant_for_wrapper() -> None:
    out = synthesize_body(_AddressGroups)
    assert "_AddressGroups(...)" not in out  # not opaque
    assert "folder=" not in out and "snippet=" not in out  # container skipped
    # FULL nesting wrapper(wrapper(leaf)) — NOT the bare `Static(...)` form the
    # real model rejects (C2). Must descend the payload sub-wrapper to its leaf.
    assert "_AddressGroups(_GroupType(_Static(" in out
    assert 'static=["example"]' in out


def test_cycle_guard_terminates() -> None:
    # required self-reference would recurse forever without the guard
    class A(BaseModel):
        nxt: A  # required cycle

    A.model_rebuild()
    out = synthesize_body(A)
    assert out == "A(\n    nxt=A(...),\n)"


# ---------------------------------------------------------------------------
# Step 3b: _enum_literal escaping
# ---------------------------------------------------------------------------


def test_enum_first_value_with_quote_is_escaped() -> None:
    class Tricky(str, enum.Enum):  # noqa: UP042
        FANCY = 'say "hi"'

    class Body(BaseModel):
        kind: Tricky

    out = synthesize_body(Body)
    # must be valid Python — the quote is escaped, not raw
    import ast

    ast.parse(out)
    assert r'"say \"hi\""' in out or "'say \"hi\"'" in out


# ---------------------------------------------------------------------------
# Task 2: reference_example + assemble_reference_docstring
# ---------------------------------------------------------------------------


class AllOptional(BaseModel):  # mirrors a PATCH body: nothing required
    name: str | None = None
    note: str | None = None


def test_reference_example_create_includes_body_and_client_path() -> None:
    ex = reference_example(
        attr="custom_app",
        method="create",
        path_args=[],
        body_model=CustomApp,
    )
    assert ex is not None
    assert ex.startswith("**Example:**\n\n```python\n")
    assert "client.custom_app.create(" in ex
    assert "body=CustomApp(" in ex
    assert ex.rstrip().endswith("```")


def test_reference_example_path_only_op_shows_client_call() -> None:
    ex = reference_example(
        attr="custom_app",
        method="get",
        path_args=[("id", "<id>")],
        body_model=None,
    )
    assert ex == (
        '**Example:**\n\n```python\nclient.custom_app.get(\n    id="<id>",\n)\n```'
    )


def test_reference_example_list_no_args() -> None:
    ex = reference_example(
        attr="custom_app",
        method="list",
        path_args=[],
        body_model=None,
    )
    assert ex == "**Example:**\n\n```python\nclient.custom_app.list()\n```"


def test_reference_example_all_optional_body_shows_nav_line_with_hint() -> None:
    # D2 (updated): an empty all-optional body is NOT suppressed — show the nav
    # line + an empty, valid body + an optionality hint.
    ex = reference_example(
        attr="custom_app",
        method="update",
        path_args=[("id", "<id>")],
        body_model=AllOptional,
    )
    assert ex is not None
    assert "client.custom_app.update(" in ex
    assert 'id="<id>"' in ex
    assert "body=AllOptional()" in ex
    assert "# all fields optional" in ex
    # the empty body must be valid Python (strip the markdown fence, then parse)
    import ast

    code = ex.split("```python\n", 1)[1].rsplit("\n```", 1)[0]
    ast.parse(code)


def test_reference_example_override_is_used_verbatim() -> None:
    # D6: an authored override is shown even when the synthesized body would be empty.
    override = (
        'updated = client.custom_app.update(id="abc", body=AllOptional(name="x"))'
    )
    ex = reference_example(
        attr="custom_app",
        method="update",
        path_args=[("id", "<id>")],
        body_model=AllOptional,
        override=override,
    )
    assert ex == (
        "**Example:**\n\n```python\n"
        'updated = client.custom_app.update(id="abc", body=AllOptional(name="x"))\n'
        "```"
    )


def test_assemble_docstring_single_line_when_no_example() -> None:
    assert assemble_reference_docstring("Delete a thing.", None) == "Delete a thing."


def test_assemble_docstring_indents_continuation_to_eight_spaces() -> None:
    doc = assemble_reference_docstring(
        "Create a thing.",
        "**Example:**\n\n```python\nclient.x.create()\n```",
    )
    lines = doc.split("\n")
    # summary stays flush (line 1); blank lines not indented; continuation +8 spaces
    assert lines[0] == "Create a thing."
    assert lines[1] == ""
    assert lines[2] == "        **Example:**"
    assert "        client.x.create()" in lines
