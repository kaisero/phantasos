"""Typed, object-granular resource wrappers for ``alpha`` (hand-authored fixture).

Mirrors the real generated ``extras/resources.py`` surface: each ``<Object>Resource``
wraps a backing ``*Api`` with clean verb methods and a ``_bindings`` table (clean verb
-> backing raw ops). ``cli_operations`` reads ``raw_method``/``body`` from each binding;
``_select``/``_to_raw``/``_call`` make the wrapper genuinely dispatchable.

The binding shape (incl. ``enums`` + ``serialize_name``) and the
``_call(verb, present, kwargs)`` signature match ``fakesdk`` so the offline dispatch
path is faithful. ponytail: still trimmed — no pagination/``--all`` seam (unused offline).
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

    def _serialize(self, verb: str, **kwargs: Any) -> tuple[str, str, dict, Any]:
        """The dry-run seam: return the (method, url, headers, body) the live call
        would build — without performing it. A trimmed analog of the real wrapper's
        ``_serialize`` (which delegates to OAG's ``<op>_serialize`` named by
        ``serialize_name``); enough to prove the runtime navigates
        ``client.<sub>.<object>._serialize(...)`` per-sub."""
        present = {k for k, v in kwargs.items() if v is not None}
        b = self._select(verb, present)
        raw = self._to_raw(kwargs, b)
        body = raw.get(b["body"]) if b["body"] else None
        if hasattr(body, "model_dump"):  # OAG's serialize returns a JSON-ready body
            body = body.model_dump(by_alias=True)
        return ("POST", f"https://fedsdk.test/{b['raw_method']}", {}, body)


class WidgetResource(_ResourceBase):
    """Typed wrapper for ``widget`` (backed by ``WidgetsApi``)."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "create": [
            {
                "raw_method": "create_widget",
                "serialize_name": "_create_widget_serialize",
                "requires": [],
                "param_map": {},
                "body": "widget_input",
                "enums": {},
            }
        ],
        "get": [
            {
                "raw_method": "get_widget_by_id",
                "serialize_name": "_get_widget_by_id_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
                "enums": {},
            }
        ],
        "list": [
            {
                "raw_method": "list_widgets",
                "serialize_name": "_list_widgets_serialize",
                "requires": [],
                "param_map": {"limit": "limit"},
                "body": None,
                "enums": {},
            }
        ],
        "update": [
            {
                "raw_method": "update_widget",
                "serialize_name": "_update_widget_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "widget_input",
                "enums": {},
            }
        ],
        "delete": [
            {
                "raw_method": "delete_widget_by_id",
                "serialize_name": "_delete_widget_by_id_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
                "enums": {},
            }
        ],
    }

    def create(self, body: WidgetInput | None = None) -> Widget:
        return self._call(
            "create",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )

    def get(self, id: str | None = None) -> Widget:
        return self._call("get", {k for k, v in {"id": id}.items() if v is not None}, {"id": id})

    def list(self, limit: int | None = None) -> WidgetList:
        return self._call(
            "list",
            {k for k, v in {"limit": limit}.items() if v is not None},
            {"limit": limit},
        )

    def update(self, id: str | None = None, body: WidgetInput | None = None) -> Widget:
        return self._call(
            "update",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )

    def delete(self, id: str | None = None) -> None:
        return self._call("delete", {k for k, v in {"id": id}.items() if v is not None}, {"id": id})
