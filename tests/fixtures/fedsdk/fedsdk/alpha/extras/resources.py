"""Typed, object-granular resource wrappers for ``alpha`` (hand-authored fixture).

Mirrors the real generated ``extras/resources.py`` surface: each ``<Object>Resource``
wraps a backing ``*Api`` with clean verb methods and a ``_bindings`` table (clean verb
-> backing raw ops). ``cli_operations`` reads ``raw_method``/``body`` from each binding;
``_select``/``_to_raw``/``_call`` make the wrapper genuinely dispatchable.

ponytail: a trimmed copy of fakesdk's ``_ResourceBase`` — no pagination/serialize
seams (unused offline). Add them if a federated task needs --all or dry-run paths.
"""

from __future__ import annotations

from typing import Any, ClassVar

from ..models import Widget, WidgetInput, WidgetList


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
        for wrapper_name, raw_name in b["param_map"].items():
            value = kwargs.get(wrapper_name)
            if value is not None:
                raw[raw_name] = value
        if b["body"] is not None and kwargs.get("body") is not None:
            raw[b["body"]] = kwargs["body"]
        return raw

    def _call(self, verb: str, kwargs: dict[str, Any]) -> Any:
        present = {k for k, v in kwargs.items() if v is not None}
        b = self._select(verb, present)
        return getattr(self._api, b["raw_method"])(**self._to_raw(kwargs, b))


class WidgetResource(_ResourceBase):
    """Typed wrapper for ``widget`` (backed by ``WidgetsApi``)."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "create": [
            {
                "raw_method": "create_widget",
                "requires": [],
                "param_map": {},
                "body": "widget_input",
            }
        ],
        "get": [
            {
                "raw_method": "get_widget_by_id",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
            }
        ],
        "list": [
            {
                "raw_method": "list_widgets",
                "requires": [],
                "param_map": {"limit": "limit"},
                "body": None,
            }
        ],
        "update": [
            {
                "raw_method": "update_widget",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "widget_input",
            }
        ],
        "delete": [
            {
                "raw_method": "delete_widget_by_id",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
            }
        ],
    }

    def create(self, body: WidgetInput | None = None) -> Widget:
        return self._call("create", {"body": body})

    def get(self, id: str | None = None) -> Widget:
        return self._call("get", {"id": id})

    def list(self, limit: int | None = None) -> WidgetList:
        return self._call("list", {"limit": limit})

    def update(self, id: str | None = None, body: WidgetInput | None = None) -> Widget:
        return self._call("update", {"id": id, "body": body})

    def delete(self, id: str | None = None) -> None:
        return self._call("delete", {"id": id})
