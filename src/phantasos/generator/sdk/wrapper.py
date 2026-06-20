"""SDK operation-override helpers.

This module provides build-time validation and resolution of the ``operations:``
block in a product's ``sdk.yml``.  Each override is keyed by ``resource.method``
(matching the ``OperationInventory`` introspection key) and may rename the
object, method, or verb surface of a generated CLI command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from phantasos.config import OperationOverride
    from phantasos.generator.opmodel.inventory import OperationInventory


def validate_override_keys(
    inv: OperationInventory,
    overrides: dict[str, OperationOverride],
) -> None:
    """Raise ``ValueError`` if any override key is not a valid ``resource.method``.

    Args:
        inv: The introspected OperationInventory.
        overrides: Mapping of ``"resource.method"`` to OperationOverride instances.

    Raises:
        ValueError: When one or more keys in *overrides* do not match any
            operation in *inv*.
    """
    keys = {f"{op.resource}.{op.method}" for op in inv.operations}
    unknown = set(overrides) - keys
    if unknown:
        raise ValueError(
            "sdk.yml operations: unknown operation key(s): "
            f"{', '.join(sorted(unknown))}"
        )
