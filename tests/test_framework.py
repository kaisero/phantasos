"""Offline unit tests for the phantasos framework engine."""

from pathlib import Path
from typing import Any

from phantasos.generator.sdk import patches, preprocess, render


def test_collapse_allof_over_array_ref() -> None:
    spec: dict[str, Any] = {
        "components": {
            "schemas": {
                "Arr": {"type": "array", "items": {"type": "string"}},
                "S": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "allOf": [
                                {"$ref": "#/components/schemas/Arr"},
                                {"description": "d"},
                            ]
                        }
                    },
                },
            }
        }
    }
    stats = {"allof_collapsed": 0, "mojibake_fixed": 0, "enum_dups_removed": 0}
    preprocess.clean(spec, stats)
    assert spec["components"]["schemas"]["S"]["properties"]["x"] == {"$ref": "#/components/schemas/Arr"}
    assert stats["allof_collapsed"] == 1


def test_allof_over_object_ref_preserved() -> None:
    spec: dict[str, Any] = {
        "components": {
            "schemas": {
                "Obj": {"type": "object", "properties": {"a": {"type": "string"}}},
                "S": {
                    "type": "object",
                    "properties": {"x": {"allOf": [{"$ref": "#/components/schemas/Obj"}]}},
                },
            }
        }
    }
    stats = {"allof_collapsed": 0, "mojibake_fixed": 0, "enum_dups_removed": 0}
    preprocess.clean(spec, stats)
    assert "allOf" in spec["components"]["schemas"]["S"]["properties"]["x"]


def test_mojibake_and_enum_dedupe() -> None:
    spec: dict[str, Any] = {"components": {"schemas": {"E": {"enum": ["TelefÃ³nica S.A.", "Telefónica S.A."]}}}}
    stats = {"allof_collapsed": 0, "mojibake_fixed": 0, "enum_dups_removed": 0}
    preprocess.clean(spec, stats)
    assert spec["components"]["schemas"]["E"]["enum"] == ["Telefónica S.A."]
    assert stats["mojibake_fixed"] == 1 and stats["enum_dups_removed"] == 1


def test_hoist_items_and_tag_operations() -> None:
    spec: dict[str, Any] = {
        "components": {
            "schemas": {
                "C": {
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                            },
                        }
                    }
                }
            }
        },
        "paths": {"/x": {"get": {"summary": "s"}}},
    }
    preprocess.hoist_items(spec, [("C", "items", "CEntry")])
    assert spec["components"]["schemas"]["C"]["properties"]["items"]["items"] == {"$ref": "#/components/schemas/CEntry"}
    assert "CEntry" in spec["components"]["schemas"]
    preprocess.tag_operations(spec, [("/x", "get", "GetX", "Things")])
    assert spec["paths"]["/x"]["get"]["operationId"] == "GetX"
    assert spec["paths"]["/x"]["get"]["tags"] == ["Things"]


def test_apostrophe_patch(tmp_path: Path) -> None:
    f = tmp_path / "e.py"
    f.write_text("class E(str, Enum):\n    A = 'Old McDonald's Farm'\n")
    assert patches.patch_apostrophe_enums(tmp_path) == 1
    assert '"Old McDonald\'s Farm"' in f.read_text()


def test_oneof_first_match_patch(tmp_path: Path) -> None:
    src = "        instance.actual_instance = RuleSummary.from_json(json_str)\n        match += 1\n"
    f = tmp_path / "m.py"
    f.write_text("actual_instance = x\nfrom_json(json_str)\n" + src)
    assert patches.patch_oneof_first_match(tmp_path) == 1
    assert "return instance" in f.read_text()


def test_render_auth_template_inlines_params() -> None:
    env = render._env()
    out = env.get_template("auth/scm_oauth.py.jinja").render(
        base_url="https://api.example.com",
        token_url="https://auth.example.com/token",
        scope_env="SCOPE",
        client_id_env="CID",
        client_secret_env="CSEC",
        base_url_env="BASE",
        config_class_name="ExampleConfiguration",
        has_retry=True,
    )
    assert 'DEFAULT_TOKEN_URL = "https://auth.example.com/token"' in out
    assert "class ExampleConfiguration(Configuration):" in out
    assert '_pick(overrides, "client_id", "CID")' in out  # jinja-rendered
    assert "{{" not in out  # no unrendered jinja


def _render_offset(**overrides: object) -> str:
    env = render._env()
    params: dict[str, object] = {
        "data_field": "data",
        "limit_field": "limit",
        "offset_field": "offset",
        "total_field": "total",
        "default_page_size": 100,
    }
    params.update(overrides)
    return env.get_template("pagination/offset.py.jinja").render(**params)


def _exec_paginate(src: str) -> Any:
    ns: dict[str, Any] = {}
    exec(compile(src, "offset.py", "exec"), ns)  # noqa: S102  (rendered SDK source)
    return ns["paginate"]


def test_render_offset_pagination_no_unrendered_jinja() -> None:
    src = _render_offset()
    assert "{{" not in src and "{%" not in src
    assert "def paginate(" in src


def test_render_offset_pagination_walks_all_pages() -> None:
    from types import SimpleNamespace

    paginate = _exec_paginate(_render_offset())
    items = list(range(250))

    def list_method(**kw: int) -> SimpleNamespace:
        off, lim = kw["offset"], kw["limit"]
        chunk = items[off : off + lim]
        return SimpleNamespace(data=chunk, total=len(items), limit=lim, offset=off)

    # default page size 100 -> 100 + 100 + 50, stop on the short final page
    assert list(paginate(list_method)) == items


def test_render_offset_pagination_respects_caller_limit() -> None:
    from types import SimpleNamespace

    paginate = _exec_paginate(_render_offset())
    items = list(range(120))
    seen_limits: list[int] = []

    def list_method(**kw: int) -> SimpleNamespace:
        seen_limits.append(kw["limit"])
        off, lim = kw["offset"], kw["limit"]
        return SimpleNamespace(data=items[off : off + lim], total=len(items), limit=lim, offset=off)

    assert list(paginate(list_method, limit=50)) == items
    assert seen_limits == [50, 50, 50]  # 50 + 50 + 20 (short) -> 3 calls


def test_render_offset_pagination_total_guard_stops_runaway() -> None:
    from types import SimpleNamespace

    paginate = _exec_paginate(_render_offset())
    calls = {"n": 0}

    # A buggy endpoint that ignores offset and always returns a FULL page would loop
    # forever on the short-page rule alone; the offset>=total guard must stop it.
    def list_method(**kw: int) -> SimpleNamespace:
        calls["n"] += 1
        if calls["n"] > 5:
            raise AssertionError("paginate did not stop — total guard missing")
        lim = kw["limit"]
        return SimpleNamespace(data=list(range(lim)), total=lim, limit=lim, offset=kw["offset"])

    out = list(paginate(list_method))
    assert len(out) == 100  # one full page, then offset(100) >= total(100) -> stop
    assert calls["n"] == 1


def _render_facade(*, has_auth: bool, has_pagination: bool) -> str:
    env = render._env()
    result: str = env.get_template("facade/client.py.jinja").render(
        resources=[{"module": "things_api", "cls": "ThingsApi", "attr": "things"}],
        has_auth=has_auth,
        has_pagination=has_pagination,
    )
    return result


def test_render_facade_full_components() -> None:
    out = _render_facade(has_auth=True, has_pagination=True)
    assert "from .auth import api_client_from_credentials, api_client_from_env" in out
    assert "from .pagination import paginate" in out
    assert "def from_env(" in out and "def paginate(" in out
    assert "{%" not in out and "{{" not in out


def test_render_facade_omits_absent_components() -> None:
    # A spec like ADEM: auth but no pagination/errors.
    out = _render_facade(has_auth=True, has_pagination=False)
    assert "from .auth import" in out and "def from_env(" in out
    assert "from .pagination" not in out  # no dangling import
    assert "def paginate(" not in out  # no method referencing missing module
    assert "things: ThingsApi" in out  # resources still bound
    assert "{%" not in out and "{{" not in out

    # And the fully-bare case: facade only.
    bare = _render_facade(has_auth=False, has_pagination=False)
    assert "from .auth" not in bare and "from .pagination" not in bare
    assert "def from_env(" not in bare and "def paginate(" not in bare
