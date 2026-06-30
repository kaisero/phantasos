"""Typed, object-granular resource wrappers for ``beta`` (hand-authored fixture).

Mirrors ``alpha``'s wrapper surface but adds a non-CRUD action (``compute``) on the
``gadget`` object — the clean verb that is NOT create/get/list/update/delete, which
federated classification/dispatch must carry through.

The binding shape (incl. ``enums`` + ``serialize_name``) and the
``_call(verb, present, kwargs)`` signature match ``fakesdk``. ponytail: trimmed —
no pagination/``--all`` seam (unused offline).
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..models import Gadget, GadgetInput, GadgetList, Status


class _ResourceBase:
    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {}

    def __init__(self, api: Any) -> None:
        self._api = api

    def _select(self, verb: str, present: set[str]) -> dict[str, Any]:
        cands = [b for b in self._bindings[verb] if set(b["requires"]) <= present]
        if not cands:
            raise ValueError(f"{verb}: missing required arg(s)")
        return max(cands, key=lambda b: len(b["requires"]))

    def _to_raw(self, kwargs: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        enums = b["enums"]
        for wrapper_name, raw_name in b["param_map"].items():
            value = kwargs.get(wrapper_name)
            if value is None:
                continue
            if wrapper_name in enums and isinstance(value, str):
                value = globals()[enums[wrapper_name]](value)
            raw[raw_name] = value
        if b["body"] is not None and kwargs.get("body") is not None:
            raw[b["body"]] = kwargs["body"]
        return raw

    def _call(self, verb: str, present: set[str], kwargs: dict[str, Any]) -> Any:
        b = self._select(verb, present)
        return getattr(self._api, b["raw_method"])(**self._to_raw(kwargs, b))


class GadgetResource(_ResourceBase):
    """Typed wrapper for ``gadget`` (backed by ``GadgetsApi``); adds ``compute``."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "create": [
            {
                "raw_method": "create_gadget",
                "serialize_name": "_create_gadget_serialize",
                "requires": [],
                "param_map": {},
                "body": "gadget_input",
                "enums": {},
            }
        ],
        "get": [
            {
                "raw_method": "get_gadget_by_id",
                "serialize_name": "_get_gadget_by_id_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
                "enums": {},
            }
        ],
        "list": [
            {
                "raw_method": "list_gadgets",
                "serialize_name": "_list_gadgets_serialize",
                "requires": [],
                "param_map": {"limit": "limit"},
                "body": None,
                "enums": {},
            }
        ],
        "update": [
            {
                "raw_method": "update_gadget",
                "serialize_name": "_update_gadget_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "gadget_input",
                "enums": {},
            }
        ],
        "delete": [
            {
                "raw_method": "delete_gadget_by_id",
                "serialize_name": "_delete_gadget_by_id_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
                "enums": {},
            }
        ],
        "compute": [
            {
                "raw_method": "compute_gadget",
                "serialize_name": "_compute_gadget_serialize",
                "requires": [],
                "param_map": {},
                "body": "gadget_input",
                "enums": {},
            }
        ],
    }

    def create(self, body: GadgetInput | None = None) -> Gadget:
        return self._call(
            "create",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )

    def get(self, id: str | None = None) -> Gadget:
        return self._call(
            "get", {k for k, v in {"id": id}.items() if v is not None}, {"id": id}
        )

    def list(self, limit: int | None = None) -> GadgetList:
        return self._call(
            "list",
            {k for k, v in {"limit": limit}.items() if v is not None},
            {"limit": limit},
        )

    def update(self, id: str | None = None, body: GadgetInput | None = None) -> Gadget:
        return self._call(
            "update",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )

    def delete(self, id: str | None = None) -> None:
        return self._call(
            "delete", {k for k, v in {"id": id}.items() if v is not None}, {"id": id}
        )

    def compute(self, body: GadgetInput | None = None) -> Status:
        return self._call(
            "compute",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )
