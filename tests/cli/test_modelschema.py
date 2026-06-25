"""Unit tests for the CLI model registry walk (modelschema.py)."""

from __future__ import annotations

from pydantic import BaseModel

from phantasos.generator.cli.modelschema import registry_from_models


class CreateMicrosoftProviderRequest(BaseModel):
    """
    Request body to create a Microsoft OneDrive provider.
    """

    tenant_id: str


class CreateOrReplaceAppGroupInput(BaseModel):  # no real docstring below
    """CreateOrReplaceAppGroupInput"""

    name: str


def test_registry_captures_model_level_description() -> None:
    reg = registry_from_models([CreateMicrosoftProviderRequest])
    assert (
        reg["CreateMicrosoftProviderRequest"].description
        == "Request body to create a Microsoft OneDrive provider."
    )


def test_registry_drops_classname_only_docstring() -> None:
    # openapi-generator emits `"""<ClassName>"""` for description-less schemas;
    # that is noise, not a description, so it must NOT be captured.
    reg = registry_from_models([CreateOrReplaceAppGroupInput])
    assert reg["CreateOrReplaceAppGroupInput"].description == ""


def test_model_doc_extraction_cases() -> None:
    # Direct coverage of the extraction helper that BOTH ModelSchema(...) sites use
    # (the regular branch AND the is_oneof branch thread the identical _model_doc(cls)).
    from phantasos.generator.cli.modelschema import _model_doc

    class Described(BaseModel):
        """
        Multi word

        description here.
        """

    class NameOnly(BaseModel):
        """NameOnly"""

    class NoDoc(BaseModel):
        pass

    # whitespace collapsed to a single line:
    assert _model_doc(Described) == "Multi word description here."
    assert _model_doc(NameOnly) == ""  # class-name-only docstring dropped
    assert _model_doc(NoDoc) == ""  # __doc__ is None (not inherited from BaseModel)
