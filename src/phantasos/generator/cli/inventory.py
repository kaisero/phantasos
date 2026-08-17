"""Backward-compatibility shim: inventory types now live in generator.opmodel.inventory.

All public names are re-exported so existing imports continue to work unchanged.
"""

from __future__ import annotations

from ..opmodel.inventory import (
    FieldInfo,
    Location,
    OperationInfo,
    OperationInventory,
    ParamInfo,
)

__all__ = [
    "FieldInfo",
    "Location",
    "OperationInfo",
    "OperationInventory",
    "ParamInfo",
]
