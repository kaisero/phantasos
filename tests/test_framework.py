"""Offline unit tests for the sdkgen framework engine."""

from pathlib import Path
from typing import Any

from sdkgen import patches, preprocess, render


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
    assert spec["components"]["schemas"]["S"]["properties"]["x"] == {
        "$ref": "#/components/schemas/Arr"
    }
    assert stats["allof_collapsed"] == 1


def test_allof_over_object_ref_preserved() -> None:
    spec: dict[str, Any] = {
        "components": {
            "schemas": {
                "Obj": {"type": "object", "properties": {"a": {"type": "string"}}},
                "S": {
                    "type": "object",
                    "properties": {
                        "x": {"allOf": [{"$ref": "#/components/schemas/Obj"}]}
                    },
                },
            }
        }
    }
    stats = {"allof_collapsed": 0, "mojibake_fixed": 0, "enum_dups_removed": 0}
    preprocess.clean(spec, stats)
    assert "allOf" in spec["components"]["schemas"]["S"]["properties"]["x"]


def test_mojibake_and_enum_dedupe() -> None:
    spec: dict[str, Any] = {
        "components": {
            "schemas": {"E": {"enum": ["TelefÃ³nica S.A.", "Telefónica S.A."]}}
        }
    }
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
    assert spec["components"]["schemas"]["C"]["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/CEntry"
    }
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
    src = (
        "        instance.actual_instance = RuleSummary.from_json(json_str)\n"
        "        match += 1\n"
    )
    f = tmp_path / "m.py"
    f.write_text("actual_instance = x\nfrom_json(json_str)\n" + src)
    assert patches.patch_oneof_first_match(tmp_path) == 1
    assert "return instance" in f.read_text()


def test_render_auth_template_inlines_params() -> None:
    env = render._env()
    out = env.get_template("auth/oauth_client_credentials.py.jinja").render(
        base_url="https://api.example.com",
        token_url="https://auth.example.com/token",
        scope_env="SCOPE",
        client_id_env="CID",
        client_secret_env="CSEC",
        base_url_env="BASE",
        config_class_name="ExampleConfiguration",
        retry_statuses=(429, 503),
        backoff_factor=0.5,
    )
    assert 'DEFAULT_TOKEN_URL = "https://auth.example.com/token"' in out
    assert "class ExampleConfiguration(Configuration):" in out
    assert 'os.environ.get("CID")' in out
    assert "{{" not in out  # no unrendered jinja


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
