import keyword

import pytest

from phantasos.config import OperationOverride
from phantasos.generator.opmodel.inventory import OperationInfo, OperationInventory
from phantasos.generator.sdk.wrapper import (
    _clean_verb_and_method,
    validate_override_keys,
)


def _inv(*keys: str) -> OperationInventory:
    ops = [
        OperationInfo(resource=k.split(".")[0], method=k.split(".")[1]) for k in keys
    ]
    return OperationInventory(sdk_package="p", sdk_version="0", operations=ops)


def test_unknown_key_fails() -> None:
    with pytest.raises(ValueError, match="unknown operation key"):
        validate_override_keys(
            _inv("applications.list_applications"),
            {"applications.nope": OperationOverride(method="x")},
        )


def test_known_key_ok() -> None:
    validate_override_keys(
        _inv("applications.list_applications"),
        {"applications.list_applications": OperationOverride(method="list")},
    )


def test_keyword_method_name_is_escaped() -> None:
    """A verb-phrase that lands on a Python keyword must be escaped, not emitted raw.

    ``import_certificates`` anchors to the ``certificate`` object and verb-phrases
    to ``import`` — a keyword. Without the escape the wrapper renders an invalid
    ``def import(...)`` (a syntax error that ``build_wrapper_context`` never raises
    on). The final method name must be the safe ``import_``.
    """
    op = OperationInfo(resource="certificates", method="import_certificates")
    crud = {"certificates": {"certificate"}}
    _obj, _verb, method = _clean_verb_and_method(op, {}, crud)
    assert method == "import_"
    assert not keyword.iskeyword(method)
