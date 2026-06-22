import pytest

from phantasos.config import OperationOverride
from phantasos.generator.opmodel.inventory import OperationInfo, OperationInventory
from phantasos.generator.sdk.wrapper import validate_override_keys


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
