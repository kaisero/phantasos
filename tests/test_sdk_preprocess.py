"""Direct unit tests for the generic spec-preprocessing transforms.

These feed real, minimal OpenAPI dict fragments to the REAL functions in
`phantasos.generator.sdk.preprocess` (no mocking of the system under test) and
assert their observable behavior — exercising the recursion guard / allOf /
properties branches of `_resolve_type`, the `collapse_allof` merge, the
latin-1->utf-8 mojibake repair, and the `hoist_items` / `tag_operations`
skip-and-apply paths that the build-driven tests never reach directly.
"""

import copy
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


def test_fold_server_prefix_prepends_matched_server_path() -> None:
    from phantasos.generator.sdk.preprocess import fold_server_prefix

    spec: dict[str, Any] = {
        "servers": [
            {"url": "https://api.strata.paloaltonetworks.com/config/objects/v1"},
            {"url": "https://api.sase.paloaltonetworks.com/sse/config/v1"},
        ],
        "paths": {"/addresses": {"get": {}}, "/services": {"post": {}}},
    }
    stats: dict[str, int] = {}
    fold_server_prefix(spec, "https://api.strata.paloaltonetworks.com", stats)
    assert set(spec["paths"]) == {
        "/config/objects/v1/addresses",
        "/config/objects/v1/services",
    }
    # path-item bodies preserved, only the keys gained the prefix
    assert spec["paths"]["/config/objects/v1/addresses"] == {"get": {}}
    # servers pinned to the bare host so the host override can't double the prefix
    assert spec["servers"] == [{"url": "https://api.strata.paloaltonetworks.com"}]
    assert stats["server_prefix_folded"] == 2


def test_fold_server_prefix_noop_for_in_path_prefix() -> None:
    # incidents/posture style: bare host server, prefix already in the path keys
    from phantasos.generator.sdk.preprocess import fold_server_prefix

    spec: dict[str, Any] = {
        "servers": [{"url": "https://api.strata.paloaltonetworks.com"}],
        "paths": {"/incidents/v1/search": {"get": {}}},
    }
    fold_server_prefix(spec, "https://api.strata.paloaltonetworks.com")
    assert set(spec["paths"]) == {"/incidents/v1/search"}


def test_fold_server_prefix_noop_when_no_matching_host() -> None:
    # only a sase server; base_url is strata -> no match -> untouched
    from phantasos.generator.sdk.preprocess import fold_server_prefix

    spec: dict[str, Any] = {
        "servers": [{"url": "https://api.sase.paloaltonetworks.com/sse/config/v1"}],
        "paths": {"/x": {"get": {}}},
    }
    fold_server_prefix(spec, "https://api.strata.paloaltonetworks.com")
    assert set(spec["paths"]) == {"/x"}


def test_spec_declares_header_component_param() -> None:
    from phantasos.generator.sdk.preprocess import spec_declares_header

    spec: dict[str, Any] = {
        "components": {
            "parameters": {"Region": {"in": "header", "name": "x-panw-region"}}
        },
        "paths": {},
    }
    assert spec_declares_header(spec, "x-panw-region")
    assert spec_declares_header(spec, "X-PANW-Region")  # case-insensitive
    assert not spec_declares_header(spec, "prisma-tenant")


def test_spec_declares_header_inline_op_param() -> None:
    from phantasos.generator.sdk.preprocess import spec_declares_header

    spec: dict[str, Any] = {
        "paths": {
            "/x": {"get": {"parameters": [{"in": "header", "name": "X-PANW-Region"}]}}
        },
    }
    assert spec_declares_header(spec, "x-panw-region")


def test_spec_declares_header_absent_or_non_header() -> None:
    from phantasos.generator.sdk.preprocess import spec_declares_header

    spec: dict[str, Any] = {
        "components": {"parameters": {"Folder": {"in": "query", "name": "folder"}}},
        "paths": {"/x": {"get": {"parameters": [{"in": "query", "name": "limit"}]}}},
    }
    assert not spec_declares_header(spec, "x-panw-region")  # only query params


def test_resolve_sub_host_shared_when_server_matches_base() -> None:
    from phantasos.generator.sdk.preprocess import resolve_sub_host

    base = "https://api.strata.paloaltonetworks.com"
    spec: dict[str, Any] = {
        "servers": [
            {"url": "https://api.strata.paloaltonetworks.com/config/objects/v1"}
        ]
    }
    assert resolve_sub_host(spec, base) == base


def test_resolve_sub_host_overrides_when_different_gateway() -> None:
    from phantasos.generator.sdk.preprocess import resolve_sub_host

    base = "https://api.strata.paloaltonetworks.com"
    spec: dict[str, Any] = {
        "servers": [{"url": "https://api.sase.paloaltonetworks.com"}]
    }
    assert resolve_sub_host(spec, base) == "https://api.sase.paloaltonetworks.com"


def test_resolve_sub_host_falls_back_to_base_when_no_servers() -> None:
    from phantasos.generator.sdk.preprocess import resolve_sub_host

    base = "https://api.strata.paloaltonetworks.com"
    assert resolve_sub_host({}, base) == base


# ---- flatten_scm_bodies ---------------------------------------------------------
# openapi-generator keeps only the composition (oneOf/anyOf) when a schema has
# `properties` + a sibling oneOf/anyOf, dropping the payload. `flatten_scm_bodies`
# lifts each reachable leaf property back onto `properties` — but ONLY for SCM
# "configurable objects", recognized by the placement marker {folder,snippet,device}
# appearing in the reachable leaf set. Everything else (the 15 real discriminated
# unions) is left untouched.


def test_flatten_placement_only_schema_flattens_and_keeps_real_schema() -> None:
    # The base case: {properties:{name}, oneOf:[folder, snippet, device]} -> a flat
    # model carrying name + all three placement options, oneOf removed. The lifted
    # `folder` keeps its REAL schema (maxLength), not a synthesized bare string, and
    # the placement options are optional (never added to `required`).
    spec = _spec_with(
        {
            "Tag": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string", "maxLength": 63}},
                "oneOf": [
                    {
                        "type": "object",
                        "title": "folder",
                        "properties": {"folder": {"type": "string", "maxLength": 64}},
                        "required": ["folder"],
                    },
                    {
                        "type": "object",
                        "title": "snippet",
                        "properties": {"snippet": {"type": "string"}},
                        "required": ["snippet"],
                    },
                    {
                        "type": "object",
                        "title": "device",
                        "properties": {"device": {"type": "string"}},
                        "required": ["device"],
                    },
                ],
            }
        }
    )
    stats: defaultdict[str, int] = defaultdict(int)
    p.flatten_scm_bodies(spec, stats)
    s = spec["components"]["schemas"]["Tag"]
    assert "oneOf" not in s
    assert "anyOf" not in s
    assert set(s["properties"]) == {"name", "folder", "snippet", "device"}
    # real property schema lifted intact (merge-don't-clobber, not bare string)
    assert s["properties"]["folder"] == {"type": "string", "maxLength": 64}
    # placement options are optional, not added to required
    assert s["required"] == ["name"]
    assert stats["flatten_scm_bodies"] == 1


def test_flatten_membership_plus_placement_merges_all_leaves() -> None:
    # addresses-style: anyOf[ oneOf(value types), oneOf(placement) ]. Every value
    # leaf and every placement leaf is merged onto `properties` (all optional).
    spec = _spec_with(
        {
            "Address": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "anyOf": [
                    {
                        "title": "address_type",
                        "oneOf": [
                            {
                                "properties": {"ip_netmask": {"type": "string"}},
                                "required": ["ip_netmask"],
                            },
                            {
                                "properties": {"fqdn": {"type": "string"}},
                                "required": ["fqdn"],
                            },
                        ],
                    },
                    {
                        "title": "container_type",
                        "oneOf": [
                            {
                                "properties": {"folder": {"type": "string"}},
                                "required": ["folder"],
                            },
                            {
                                "properties": {"snippet": {"type": "string"}},
                                "required": ["snippet"],
                            },
                            {
                                "properties": {"device": {"type": "string"}},
                                "required": ["device"],
                            },
                        ],
                    },
                ],
            }
        }
    )
    stats: defaultdict[str, int] = defaultdict(int)
    p.flatten_scm_bodies(spec, stats)
    s = spec["components"]["schemas"]["Address"]
    assert "anyOf" not in s
    assert set(s["properties"]) == {
        "name",
        "ip_netmask",
        "fqdn",
        "folder",
        "snippet",
        "device",
    }
    assert stats["flatten_scm_bodies"] == 1


def test_flatten_multifield_branch_merges_every_field() -> None:
    # C1 regression guard: a nat-rules dest-translation branch carries MULTIPLE
    # properties and no `required`. `_leaf_props` must yield ALL of them, not just
    # the `required` ones — otherwise dest-NAT fields are silently dropped. The
    # placement oneOf is what makes the gate fire.
    spec = _spec_with(
        {
            "NatRules": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "anyOf": [
                    {
                        "oneOf": [
                            {
                                "title": "destination_translation",
                                "type": "object",
                                "properties": {
                                    "translated_address": {"type": "string"},
                                    "translated_port": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 65535,
                                    },
                                },
                            }
                        ]
                    },
                ],
                "oneOf": [
                    {
                        "properties": {"folder": {"type": "string"}},
                        "required": ["folder"],
                    },
                    {
                        "properties": {"snippet": {"type": "string"}},
                        "required": ["snippet"],
                    },
                    {
                        "properties": {"device": {"type": "string"}},
                        "required": ["device"],
                    },
                ],
            }
        }
    )
    stats: defaultdict[str, int] = defaultdict(int)
    p.flatten_scm_bodies(spec, stats)
    s = spec["components"]["schemas"]["NatRules"]
    assert "oneOf" not in s
    assert "anyOf" not in s
    assert "translated_address" in s["properties"]
    assert "translated_port" in s["properties"]
    # the real (integer, bounded) schema is lifted, not a synthesized string
    assert s["properties"]["translated_port"] == {
        "type": "integer",
        "minimum": 1,
        "maximum": 65535,
    }
    assert {"folder", "snippet", "device"} <= set(s["properties"])
    assert stats["flatten_scm_bodies"] == 1


def test_flatten_leaves_no_placement_union_untouched() -> None:
    # Over-reach guard: a real discriminated union with no placement marker (e.g. a
    # schedule's hourly/daily) must be left exactly as-is. No flatten, no stat bump.
    spec = _spec_with(
        {
            "Schedule": {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "oneOf": [
                    {
                        "properties": {"hourly": {"type": "array"}},
                        "required": ["hourly"],
                    },
                    {"properties": {"daily": {"type": "array"}}, "required": ["daily"]},
                ],
            }
        }
    )
    before = copy.deepcopy(spec)
    stats: defaultdict[str, int] = defaultdict(int)
    p.flatten_scm_bodies(spec, stats)
    assert spec == before
    assert "flatten_scm_bodies" not in stats


def test_flatten_collision_merges_does_not_clobber() -> None:
    # zones-style: a real `folder` property already exists AND a `folder` placement
    # branch. Merge-don't-clobber keeps the existing property untouched and adds
    # only the missing snippet/device — no `folder_1`.
    spec = _spec_with(
        {
            "Zone": {
                "type": "object",
                "properties": {
                    "folder": {"type": "string", "description": "real folder prop"}
                },
                "oneOf": [
                    {
                        "properties": {"folder": {"type": "string", "maxLength": 64}},
                        "required": ["folder"],
                    },
                    {
                        "properties": {"snippet": {"type": "string"}},
                        "required": ["snippet"],
                    },
                    {
                        "properties": {"device": {"type": "string"}},
                        "required": ["device"],
                    },
                ],
            }
        }
    )
    stats: defaultdict[str, int] = defaultdict(int)
    p.flatten_scm_bodies(spec, stats)
    s = spec["components"]["schemas"]["Zone"]
    assert s["properties"]["folder"] == {
        "type": "string",
        "description": "real folder prop",
    }
    assert "folder_1" not in s["properties"]
    assert set(s["properties"]) == {"folder", "snippet", "device"}
    assert stats["flatten_scm_bodies"] == 1
