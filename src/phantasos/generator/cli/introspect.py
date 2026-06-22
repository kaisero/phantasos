"""Backward-compatibility shim: introspect now lives in generator.opmodel.introspect.

All public names (including the private _response_info used in tests) are re-exported
so existing imports continue to work unchanged.
"""

from __future__ import annotations

from ..opmodel.introspect import (
    _enum_values,
    _response_info,
    _unwrap_optional,
    introspect,
)

__all__ = [
    "_enum_values",
    "_response_info",
    "_unwrap_optional",
    "introspect",
]
