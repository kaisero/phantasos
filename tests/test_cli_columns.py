"""Tests for build-time column derivation and cli.yml columns validation."""

import pytest

from phantasos.generator.cli.cliconfig import ColumnEntry
from phantasos.generator.cli.columns import default_columns, resolve_columns
from phantasos.generator.cli.inventory import FieldInfo


def _f(name, kind="scalar", **kw):
    return FieldInfo(name=name, annotation="str", kind=kind, required=False, **kw)


FIELDS = [
    _f("created_at"),
    _f("name"),
    _f("spec", kind="json"),
    _f("id"),
    _f("status", kind="enum", enum_values=["on", "off"]),
    _f("region"),
    _f("zone"),
    _f("weight"),
]


def test_default_columns_prefers_known_names_then_scalars_capped():
    cols = default_columns(FIELDS)
    assert [c.path for c in cols] == [
        "id", "name", "status",          # preferred order first
        "created_at", "region", "zone",  # then declaration order, cap 6
    ]
    assert all(c.header == c.path for c in cols)


def test_default_columns_excludes_json_fields():
    assert "spec" not in [c.path for c in default_columns(FIELDS)]


FIELDS_WITH_MEMBERS = [*FIELDS, _f("members", kind="json")]


def test_resolve_columns_string_shorthand_and_entry():
    cols = resolve_columns(
        ["name", ColumnEntry(header="MEMBERS", path="members[].name")],
        FIELDS_WITH_MEMBERS, "device-group",
    )
    assert (cols[0].header, cols[0].path) == ("name", "name")
    assert (cols[1].header, cols[1].path) == ("MEMBERS", "members[].name")


def test_resolve_columns_rejects_bad_jmespath_syntax():
    with pytest.raises(ValueError, match="invalid JMESPath"):
        resolve_columns(["members[].]"], FIELDS, "device-group")


def test_resolve_columns_rejects_empty_expression():
    # jmespath raises EmptyExpressionError here, which is NOT a ParseError
    # subclass — the resolver must catch the JMESPathError base.
    with pytest.raises(ValueError, match="invalid JMESPath"):
        resolve_columns([""], FIELDS, "device-group")


def test_resolve_columns_rejects_unknown_root_field():
    with pytest.raises(ValueError, match="unknown field 'nope'"):
        resolve_columns(["nope.deeper"], FIELDS, "device-group")


def test_resolve_columns_skips_root_check_when_fields_unknown():
    # No response model introspected -> syntax-only validation
    cols = resolve_columns(["anything.goes"], [], "device-group")
    assert cols[0].path == "anything.goes"


def test_resolve_columns_skips_root_check_for_non_field_roots():
    # function at root: best-effort check must not false-positive
    cols = resolve_columns(["join(', ', tags)"], [*FIELDS, _f("tags")], "x")
    assert cols[0].header == "join(', ', tags)"
