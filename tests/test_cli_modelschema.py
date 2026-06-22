from __future__ import annotations

from pydantic import BaseModel, Field

from phantasos.generator.cli.modelschema import registry_from_models


class Spec(BaseModel):
    application_ids: list[str] | None = Field(default=None, alias="applicationIds")


class Saas(BaseModel):
    access_mode: str = Field(alias="accessMode")  # required
    specific: Spec | None = None


class Apps(BaseModel):  # all-optional
    saas: Saas | None = None


class Match(BaseModel):
    url: str


class Rule(BaseModel):
    matches: list[Match]  # list[Model]


class VA(BaseModel):
    a: str


class VB(BaseModel):
    b: str


class Target(BaseModel):
    body: VA | VB  # inline oneOf field


class A(BaseModel):
    b: B | None = None


class B(BaseModel):
    a: A | None = None


A.model_rebuild()


def test_registry_dedupes_and_resolves_refs() -> None:
    reg = registry_from_models([Apps])
    assert set(reg) == {"Apps", "Saas", "Spec"}
    saas = reg["Saas"]
    assert saas.fields[0].alias == "accessMode" and saas.fields[0].required
    assert saas.fields[1].model_ref == "Spec" and not saas.fields[1].model_ref_list


def test_registry_list_of_model_marks_list() -> None:
    reg = registry_from_models([Rule])
    f = reg["Rule"].fields[0]
    assert f.model_ref == "Match" and f.model_ref_list is True


def test_registry_inline_oneof_sets_variant_refs() -> None:
    reg = registry_from_models([Target])
    f = reg["Target"].fields[0]
    assert f.variant_refs == ["VA", "VB"] and f.model_ref is None
    assert {"VA", "VB"} <= set(reg)


def test_registry_cycle_emits_each_model_once() -> None:
    reg = registry_from_models([A])
    assert set(reg) == {"A", "B"}  # no infinite expansion
    assert reg["A"].fields[0].model_ref == "B"
    assert reg["B"].fields[0].model_ref == "A"
