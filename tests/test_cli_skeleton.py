from typing import Any

from phantasos.generator.cli.ir import ModelField, ModelSchema, synth_skeleton


def _mf(name: str, **kw: Any) -> ModelField:
    kw.setdefault("alias", name)
    kw.setdefault("py_type", "str")
    kw.setdefault("kind", "scalar")
    kw.setdefault("required", False)
    return ModelField(name=name, **kw)


REGISTRY = {
    # all-optional object → non-empty guarantee picks first field (saas)
    "Apps": ModelSchema(
        fields=[
            _mf("saas", alias="saas", kind="json", model_ref="Saas"),
            _mf("private", alias="private", kind="json", model_ref="Priv"),
        ]
    ),
    "Saas": ModelSchema(
        fields=[
            _mf(
                "access_mode",
                alias="accessMode",
                kind="enum",
                required=True,
                enum_values=["none", "any"],
            ),
            _mf("specific", alias="specific", kind="json", model_ref="Spec"),
        ]
    ),
    "Priv": ModelSchema(
        fields=[
            _mf(
                "access_mode",
                alias="accessMode",
                kind="enum",
                required=True,
                enum_values=["none"],
            ),
        ]
    ),
    "Spec": ModelSchema(
        fields=[
            _mf("ids", alias="applicationIds", kind="scalar", py_type="str"),
        ]
    ),
    # list[Model] field
    "Rule": ModelSchema(
        fields=[
            _mf(
                "matches",
                alias="matches",
                kind="json",
                required=True,
                model_ref="Match",
                model_ref_list=True,
            ),
        ]
    ),
    "Match": ModelSchema(fields=[_mf("url", alias="url", required=True)]),
    # inline oneOf field (variant_refs)
    "Target": ModelSchema(
        fields=[
            _mf(
                "body",
                alias="body",
                kind="json",
                required=True,
                variant_refs=["VA", "VB"],
            ),
        ]
    ),
    "VA": ModelSchema(fields=[_mf("a", alias="a", required=True)]),
    "VB": ModelSchema(fields=[_mf("b", alias="b", required=True)]),
    # A -> B -> A cycle
    "A": ModelSchema(fields=[_mf("b", alias="b", kind="json", required=True, model_ref="B")]),
    "B": ModelSchema(fields=[_mf("a", alias="a", kind="json", required=True, model_ref="A")]),
}


def test_minimal_non_empty_guarantee() -> None:
    # all-optional Apps → first field saas → its required accessMode
    assert synth_skeleton(REGISTRY, "Apps", full=False) == {"saas": {"accessMode": "none"}}


def test_minimal_required_only_when_required_present() -> None:
    assert synth_skeleton(REGISTRY, "Saas", full=False) == {"accessMode": "none"}


def test_full_includes_optionals_recursively() -> None:
    out = synth_skeleton(REGISTRY, "Saas", full=True)
    assert out == {"accessMode": "none", "specific": {"applicationIds": "string"}}


def test_list_of_model_wraps_in_array() -> None:
    assert synth_skeleton(REGISTRY, "Rule", full=False) == {"matches": [{"url": "string"}]}


def test_inline_oneof_uses_first_variant() -> None:
    assert synth_skeleton(REGISTRY, "Target", full=False) == {"body": {"a": "string"}}


def test_cycle_breaks_to_empty_object() -> None:
    # A -> B -> A: the second A is on the path → {}
    assert synth_skeleton(REGISTRY, "A", full=True) == {"b": {"a": {}}}


def test_unknown_model_is_empty() -> None:
    assert synth_skeleton(REGISTRY, "Nope", full=True) == {}
    assert synth_skeleton(REGISTRY, None, full=True) == {}


def test_value_precedence_example_beats_default_and_synth() -> None:
    reg = {"M": ModelSchema(fields=[_mf("x", required=True, default="dflt", example="ex")])}
    assert synth_skeleton(reg, "M", full=False) == {"x": "ex"}


def test_value_precedence_default_beats_synth() -> None:
    reg = {"M": ModelSchema(fields=[_mf("x", required=True, default="dflt")])}
    assert synth_skeleton(reg, "M", full=False) == {"x": "dflt"}
