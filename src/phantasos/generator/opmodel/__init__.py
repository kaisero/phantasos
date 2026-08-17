"""Shared operation-model package: classification, introspection, and inventory."""

from .classify import (
    _SKIP_FRAGMENTS,
    _VERB_PREFIXES,
    OBJECT_OF,
    Classification,
    _singularize,
    _strip_id_suffix,
    classify_name,
    detect_id_param,
)
from .introspect import introspect
from .inventory import FieldInfo, Location, OperationInfo, OperationInventory, ParamInfo

__all__ = [
    "OBJECT_OF",
    "_SKIP_FRAGMENTS",
    "_VERB_PREFIXES",
    "Classification",
    "FieldInfo",
    "Location",
    "OperationInfo",
    "OperationInventory",
    "ParamInfo",
    "_singularize",
    "_strip_id_suffix",
    "classify_name",
    "detect_id_param",
    "introspect",
]
