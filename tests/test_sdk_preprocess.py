"""Direct unit tests for the generic spec-preprocessing transforms.

These feed real, minimal OpenAPI dict fragments to the REAL functions in
`phantasos.generator.sdk.preprocess` (no mocking of the system under test) and
assert their observable behavior — exercising the recursion guard / allOf /
properties branches of `_resolve_type`, the `collapse_allof` merge, the
latin-1->utf-8 mojibake repair, and the `hoist_items` / `tag_operations`
skip-and-apply paths that the build-driven tests never reach directly.
"""

from collections import defaultdict
from typing import Any

from phantasos.generator.sdk import preprocess as p
from phantasos.generator.sdk.preprocess import (
    clean,
    normalize_operation_ids,
    strip_external_tags,
)


# ---- _resolve_type --------------------------------------------------------------
def test_resolve_type_non_dict_node_returns_none() -> None:
    # A non-dict node (e.g. a list branch) cannot carry a type -> None.
    assert p._resolve_type({}, ["not", "a", "dict"]) is None


def test_resolve_type_ref_cycle_is_guarded() -> None:
    # A self-referential $ref must not recurse forever: the second visit of the
    # same component name short-circuits to None via the `seen` guard.
    schemas = {"A": {"$ref": "#/components/schemas/A"}}
    assert p._resolve_type(schemas, {"$ref": "#/components/schemas/A"}) is None


def test_resolve_type_follows_ref_to_concrete_type() -> None:
    # A $ref resolves through the schema map to the referent's `type`.
    schemas = {"S": {"type": "string"}}
    assert p._resolve_type(schemas, {"$ref": "#/components/schemas/S"}) == "string"


def test_resolve_type_allof_returns_first_resolvable_branch() -> None:
    # An allOf with a pure-annotation member (resolves to None, skipped) followed
    # by a typed member resolves to that typed member.
    node = {"allOf": [{"description": "doc only"}, {"type": "integer"}]}
    assert p._resolve_type({}, node) == "integer"


def test_resolve_type_properties_imply_object() -> None:
    # A node with `properties` but no explicit `type` resolves to "object".
    assert p._resolve_type({}, {"properties": {"x": {}}}) == "object"


def test_resolve_type_bare_annotation_node_returns_none() -> None:
    # A node with neither $ref/type/allOf/properties is untyped -> None.
    assert p._resolve_type({}, {"description": "x"}) is None


def test_resolve_type_allof_with_no_typed_branch_falls_through_to_properties() -> None:
    # When every allOf branch resolves to None, resolution falls through to the
    # node's own `properties` -> "object".
    node = {"allOf": [{"description": "x"}], "properties": {"y": {}}}
    assert p._resolve_type({}, node) == "object"


# ---- collapse_allof -------------------------------------------------------------
def test_collapse_allof_merges_two_member_allof() -> None:
    # allOf = [$ref-to-non-object, annotation-only] collapses to the bare $ref,
    # dropping the redundant wrapper, and bumps the stat.
    schemas: dict[str, Any] = {
        "Str": {"type": "string"},
        "Wrapper": {
            "allOf": [
                {"$ref": "#/components/schemas/Str"},
                {"description": "a doc"},
            ]
        },
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.collapse_allof(schemas, schemas, stats)
    assert schemas["Wrapper"] == {"$ref": "#/components/schemas/Str"}
    assert stats["allof_collapsed"] == 1


def test_collapse_allof_keeps_object_ref_allof() -> None:
    # When the single $ref branch resolves to an object, the allOf is preserved
    # (only non-object collapses are safe).
    schemas: dict[str, Any] = {
        "Obj": {"type": "object", "properties": {"a": {"type": "string"}}},
        "Wrapper": {"allOf": [{"$ref": "#/components/schemas/Obj"}]},
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.collapse_allof(schemas, schemas, stats)
    assert "allOf" in schemas["Wrapper"]
    assert stats["allof_collapsed"] == 0


def test_collapse_allof_leaves_multi_ref_allof_untouched() -> None:
    # A genuine intersection (two structural $ref branches) is not a redundant
    # wrapper: the outer guard fails and the allOf is preserved.
    schemas: dict[str, Any] = {
        "A": {"type": "object", "properties": {"a": {}}},
        "B": {"type": "object", "properties": {"b": {}}},
        "Wrapper": {
            "allOf": [
                {"$ref": "#/components/schemas/A"},
                {"$ref": "#/components/schemas/B"},
            ]
        },
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.collapse_allof(schemas, schemas, stats)
    assert schemas["Wrapper"]["allOf"] == [
        {"$ref": "#/components/schemas/A"},
        {"$ref": "#/components/schemas/B"},
    ]
    assert stats["allof_collapsed"] == 0


# ---- mojibake repair (_fix_mojibake / fix_strings_and_enums) --------------------
def test_fix_mojibake_repairs_latin1_utf8_round_trip() -> None:
    # "Ã©" is the classic latin-1/utf-8 corruption of "é": repaired + counted.
    stats: defaultdict[str, int] = defaultdict(int)
    assert p._fix_mojibake("CafÃ©", stats) == "Café"
    assert stats["mojibake_fixed"] == 1


def test_fix_mojibake_leaves_undecodable_string_untouched() -> None:
    # A lone "Ã" byte cannot complete a utf-8 sequence: the UnicodeDecodeError is
    # swallowed and the original value is returned unchanged (no stat bump).
    stats: defaultdict[str, int] = defaultdict(int)
    assert p._fix_mojibake("Ã", stats) == "Ã"
    assert stats["mojibake_fixed"] == 0


def test_fix_mojibake_leaves_unencodable_string_untouched() -> None:
    # "Ã" next to a char above U+00FF cannot encode as latin-1: the
    # UnicodeEncodeError is swallowed and the string is left as-is.
    stats: defaultdict[str, int] = defaultdict(int)
    value = "ÃĀ"
    assert p._fix_mojibake(value, stats) == value
    assert stats["mojibake_fixed"] == 0


def test_fix_strings_and_enums_repairs_nested_and_dedupes() -> None:
    # Walks dicts/lists, repairing mojibake in values and within enum members,
    # then dropping the duplicate that repair produced.
    node = {
        "title": "CafÃ©",
        "enum": ["CafÃ©", "Café", "tea"],
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.fix_strings_and_enums(node, stats)
    assert node["title"] == "Café"
    assert node["enum"] == ["Café", "tea"]
    # both the title and the surviving enum member were repaired
    assert stats["mojibake_fixed"] == 2
    assert stats["enum_dups_removed"] == 1


def test_fix_strings_and_enums_walks_nested_lists() -> None:
    # A plain (non-enum) nested list recurses element-by-element, repairing
    # mojibake found inside list-borne dicts.
    node = {"anyOf": [{"title": "CafÃ©"}, {"title": "ok"}]}
    stats: defaultdict[str, int] = defaultdict(int)
    p.fix_strings_and_enums(node, stats)
    assert node["anyOf"][0]["title"] == "Café"
    assert stats["mojibake_fixed"] == 1


# ---- hoist_items ----------------------------------------------------------------
def _spec_with(schemas: dict[str, Any]) -> dict[str, Any]:
    return {"components": {"schemas": schemas}}


def test_hoist_items_skips_missing_control_schema() -> None:
    # A hoist targeting a schema that does not exist is a no-op.
    spec = _spec_with({"A": {"properties": {"p": {"type": "string"}}}})
    stats: defaultdict[str, int] = defaultdict(int)
    p.hoist_items(spec, [("NoSuch", "p", "New")], stats)
    assert "New" not in spec["components"]["schemas"]
    assert "items_hoisted" not in stats


def test_hoist_items_skips_property_without_items() -> None:
    # The control schema exists but the property carries no `items` -> skipped.
    spec = _spec_with({"A": {"properties": {"p": {"type": "string"}}}})
    stats: defaultdict[str, int] = defaultdict(int)
    p.hoist_items(spec, [("A", "p", "New")], stats)
    assert "New" not in spec["components"]["schemas"]
    assert "items_hoisted" not in stats


def test_hoist_items_hoists_inline_array_item_into_component() -> None:
    # An inline array-item object is lifted into a named component and the
    # property's `items` becomes a $ref to it.
    spec = _spec_with(
        {
            "A": {
                "properties": {
                    "arr": {
                        "type": "array",
                        "items": {"type": "object", "properties": {"x": {}}},
                    }
                }
            }
        }
    )
    stats: defaultdict[str, int] = defaultdict(int)
    p.hoist_items(spec, [("A", "arr", "ArrItem")], stats)
    schemas = spec["components"]["schemas"]
    assert schemas["ArrItem"] == {"type": "object", "properties": {"x": {}}}
    assert schemas["A"]["properties"]["arr"]["items"] == {
        "$ref": "#/components/schemas/ArrItem"
    }
    assert stats["items_hoisted"] == 1


def test_hoist_items_without_stats_still_hoists() -> None:
    # The stats dict is optional; the hoist still happens when it is omitted.
    spec = _spec_with(
        {"A": {"properties": {"arr": {"type": "array", "items": {"type": "object"}}}}}
    )
    p.hoist_items(spec, [("A", "arr", "ArrItem")])
    assert "ArrItem" in spec["components"]["schemas"]


# ---- tag_operations -------------------------------------------------------------
def test_tag_operations_skips_absent_operation() -> None:
    # A (path, method) that is not present in the spec is silently skipped.
    spec = {"paths": {"/x": {"get": {"summary": "x"}}}}
    stats: defaultdict[str, int] = defaultdict(int)
    p.tag_operations(spec, [("/missing", "get", "Op", "Tag")], stats)
    assert "ops_tagged" not in stats


def test_tag_operations_adds_operation_id_and_tag() -> None:
    # A present, untagged operation gains the operationId + tag.
    spec: dict[str, Any] = {"paths": {"/x": {"get": {"summary": "do x"}}}}
    stats: defaultdict[str, int] = defaultdict(int)
    p.tag_operations(spec, [("/x", "get", "OpId", "Tag")], stats)
    op = spec["paths"]["/x"]["get"]
    assert op["operationId"] == "OpId"
    assert op["tags"] == ["Tag"]
    assert stats["ops_tagged"] == 1


def test_tag_operations_preserves_existing_id_and_tags() -> None:
    # setdefault must not clobber an existing operationId or non-empty tags.
    spec: dict[str, Any] = {
        "paths": {"/y": {"post": {"operationId": "Keep", "tags": ["T0"]}}}
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.tag_operations(spec, [("/y", "post", "New", "Tnew")], stats)
    op = spec["paths"]["/y"]["post"]
    assert op["operationId"] == "Keep"
    assert op["tags"] == ["T0"]


def test_tag_operations_without_stats_still_tags() -> None:
    # The stats dict is optional; tagging still happens when it is omitted.
    spec: dict[str, Any] = {"paths": {"/x": {"get": {"summary": "do x"}}}}
    p.tag_operations(spec, [("/x", "get", "OpId", "Tag")])
    assert spec["paths"]["/x"]["get"]["operationId"] == "OpId"


# ---- clean (integration of the generic transforms) ------------------------------
def test_clean_runs_collapse_and_mojibake_over_a_spec() -> None:
    spec = {
        "components": {
            "schemas": {
                "Str": {"type": "string"},
                "Wrapper": {
                    "allOf": [
                        {"$ref": "#/components/schemas/Str"},
                        {"description": "CafÃ©"},
                    ]
                },
            }
        }
    }
    stats: defaultdict[str, int] = defaultdict(int)
    p.clean(spec, stats)
    assert spec["components"]["schemas"]["Wrapper"] == {
        "$ref": "#/components/schemas/Str"
    }
    assert stats["allof_collapsed"] == 1


# ---- normalize_operation_ids ----------------------------------------------------
def test_normalize_strips_suffix_and_dots() -> None:
    spec = {
        "paths": {
            "/cg": {
                "post": {"operationId": "create.connector_group.v2"},
                "get": {"operationId": "list.connector_groups.v2"},
            }
        }
    }
    normalize_operation_ids(
        spec, strip_suffix=".v2", dots_to_underscore=True, unify_separator="_"
    )
    ops = spec["paths"]["/cg"]
    assert ops["post"]["operationId"] == "create_connector_group"
    assert ops["get"]["operationId"] == "list_connector_groups"


def test_normalize_skips_missing_paths_and_operation_id() -> None:
    # No `paths` key, and an op without `operationId`, are both no-ops.
    no_paths: dict[str, Any] = {}
    normalize_operation_ids(no_paths, strip_suffix=".v2", dots_to_underscore=True)
    assert no_paths == {}

    spec = {"paths": {"/x": {"get": {"summary": "no id"}}}}
    normalize_operation_ids(spec, dots_to_underscore=True)
    assert "operationId" not in spec["paths"]["/x"]["get"]


def test_normalize_unifies_dashes_and_counts() -> None:
    # unify_separator also folds dashes; stats counts each rewritten op.
    spec = {"paths": {"/x": {"get": {"operationId": "list-foo-bar"}}}}
    stats: defaultdict[str, int] = defaultdict(int)
    normalize_operation_ids(spec, unify_separator="_", stats=stats)
    assert spec["paths"]["/x"]["get"]["operationId"] == "list_foo_bar"
    assert stats["operation_ids_normalized"] == 1


# ---- strip_external_tags --------------------------------------------------------
def test_strip_external_tags_removes_top_level_key() -> None:
    spec = {"openapi": "3.0.0", "ExternalTags": [{"name": "x"}], "paths": {}}
    stats: dict[str, int] = {}
    strip_external_tags(spec, stats)
    assert "ExternalTags" not in spec
    assert stats.get("external_tags_stripped", 0) == 1


def test_clean_invokes_strip_external_tags() -> None:
    spec = {"openapi": "3.0.0", "ExternalTags": [], "paths": {}}
    clean(spec, {})
    assert "ExternalTags" not in spec
