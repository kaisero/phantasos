"""Typed, object-granular resource wrappers (hand-authored fixture).

Mirrors the real generated ``extras/resources.py`` surface: each
``<Object>Resource`` wraps a backing ``*Api`` with clean, verb-named methods and
a ``_bindings`` table (clean verb -> backing raw ops). ``_select`` picks the
most-specific binding whose required args are all present; ``_to_raw`` renames
wrapper params to the raw names (and ``body`` to the raw body-param) and coerces
enum strings. ``_serialize`` is the dry-run seam.

Kept deliberately faithful to the emitted code so the runtime exercises the same
dispatch / pagination / serialize paths it will against the real SDK.
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar

from ..api import GizmosApi, ThingsApi, WidgetsApi
from ..models import (
    CreateGizmoInput,
    CreateWidget201Response,
    Widget,
    WidgetInput,
    WidgetList,
    WidgetType,
)
from .pagination import paginate


class _ResourceBase:
    """Shared dispatch/serialize machinery (identical to the emitted wrappers)."""

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

    def _fetch(self, verb: str, present: set[str], kwargs: dict[str, Any]) -> Any:
        return self._call(verb, present, kwargs)

    def _list(
        self, verb: str, present: set[str], kwargs: dict[str, Any], all_pages: bool
    ) -> Any:
        b = self._select(verb, present)
        fn = getattr(self._api, b["raw_method"])
        raw = self._to_raw(kwargs, b)
        page = fn(**raw)
        if not all_pages:
            return page
        items = list(paginate(fn, **raw))
        return page.model_copy(update={"data": items})

    def _serialize(self, verb: str, **kwargs: Any) -> Any:
        present = {k for k, v in kwargs.items() if v is not None}
        b = self._select(verb, present)
        fn = getattr(self._api, b["serialize_name"])
        params = {
            k: (0 if k == "_host_index" else None)
            for k in inspect.signature(fn).parameters
            if k != "self"
        }
        params.update(self._to_raw(kwargs, b))
        return fn(**params)


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
        "get": [
            {
                "raw_method": "get_widget_by_id",
                "serialize_name": "_get_widget_by_id_serialize",
                "requires": ["id"],
                "param_map": {
                    "id": "id",
                    "configuration_version": "configuration_version",
                },
                "body": None,
                "enums": {},
            }
        ],
        "list": [
            {
                "raw_method": "list_widgets",
                "serialize_name": "_list_widgets_serialize",
                "requires": [],
                "param_map": {"name": "name", "limit": "limit"},
                "body": None,
                "enums": {},
            }
        ],
        "reorder": [
            {
                "raw_method": "update_widget_positions",
                "serialize_name": "_update_widget_positions_serialize",
                "requires": [],
                "param_map": {},
                "body": "body",
                "enums": {},
            }
        ],
        "replace": [
            {
                "raw_method": "update_widget",
                "serialize_name": "_update_widget_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "widget_input",
                "enums": {},
            }
        ],
        "revoke": [
            {
                "raw_method": "revoke_widget",
                "serialize_name": "_revoke_widget_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "widget_input",
                "enums": {},
            }
        ],
        "suspend": [
            {
                "raw_method": "suspend_widget",
                "serialize_name": "_suspend_widget_serialize",
                "requires": [],
                "param_map": {},
                "body": "widget_input",
                "enums": {},
            }
        ],
        "update": [
            {
                "raw_method": "patch_widget",
                "serialize_name": "_patch_widget_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "widget_input",
                "enums": {},
            }
        ],
    }

    def __init__(self, api: WidgetsApi) -> None:
        self._api = api

    def create(self, body: WidgetInput | None = None) -> CreateWidget201Response:
        return self._call(
            "create",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )

    def delete(self, id: str | None = None) -> None:
        return self._call(
            "delete", {k for k, v in {"id": id}.items() if v is not None}, {"id": id}
        )

    def get(
        self, id: str | None = None, configuration_version: str | None = None
    ) -> Widget:
        return self._fetch(
            "get",
            {
                k
                for k, v in {
                    "id": id,
                    "configuration_version": configuration_version,
                }.items()
                if v is not None
            },
            {"id": id, "configuration_version": configuration_version},
        )

    def list(
        self,
        name: str | None = None,
        limit: int | None = None,
        *,
        all_pages: bool = False,
    ) -> WidgetList:
        return self._list(
            "list",
            {k for k, v in {"name": name, "limit": limit}.items() if v is not None},
            {"name": name, "limit": limit},
            all_pages,
        )

    def reorder(self, body: dict | None = None) -> None:
        return self._call(
            "reorder",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )

    def replace(self, id: str | None = None, body: WidgetInput | None = None) -> Widget:
        return self._call(
            "replace",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )

    def revoke(self, id: str | None = None, body: WidgetInput | None = None) -> None:
        return self._call(
            "revoke",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )

    def suspend(self, body: WidgetInput | None = None) -> None:
        return self._call(
            "suspend",
            {k for k, v in {"body": body}.items() if v is not None},
            {"body": body},
        )

    def update(self, id: str | None = None, body: WidgetInput | None = None) -> Widget:
        return self._call(
            "update",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )


class GizmoResource(_ResourceBase):
    """Typed wrapper for ``gizmo`` (backed by ``GizmosApi``)."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "create": [
            {
                "raw_method": "create_gizmo",
                "serialize_name": "_create_gizmo_serialize",
                "requires": ["type"],
                "param_map": {"type": "type"},
                "body": "create_gizmo_input",
                "enums": {"type": "WidgetType"},
            }
        ],
        "delete": [
            {
                "raw_method": "delete_gizmo_by_id",
                "serialize_name": "_delete_gizmo_by_id_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": None,
                "enums": {},
            }
        ],
        "get": [
            {
                "raw_method": "get_gizmo_by_type_and_id",
                "serialize_name": "_get_gizmo_by_type_and_id_serialize",
                "requires": ["type", "id"],
                "param_map": {"type": "type", "id": "id"},
                "body": None,
                "enums": {"type": "WidgetType"},
            }
        ],
        "list": [
            {
                "raw_method": "list_gizmos",
                "serialize_name": "_list_gizmos_serialize",
                "requires": [],
                "param_map": {},
                "body": None,
                "enums": {},
            }
        ],
        "update": [
            {
                "raw_method": "patch_gizmo",
                "serialize_name": "_patch_gizmo_serialize",
                "requires": ["id"],
                "param_map": {"id": "id"},
                "body": "create_gizmo_input",
                "enums": {},
            }
        ],
    }

    def __init__(self, api: GizmosApi) -> None:
        self._api = api

    def create(
        self, type: WidgetType | None = None, body: CreateGizmoInput | None = None
    ) -> None:
        return self._call(
            "create",
            {k for k, v in {"type": type, "body": body}.items() if v is not None},
            {"type": type, "body": body},
        )

    def delete(self, id: str | None = None) -> None:
        return self._call(
            "delete", {k for k, v in {"id": id}.items() if v is not None}, {"id": id}
        )

    def get(self, type: WidgetType | None = None, id: str | None = None) -> None:
        return self._fetch(
            "get",
            {k for k, v in {"type": type, "id": id}.items() if v is not None},
            {"type": type, "id": id},
        )

    def list(self, *, all_pages: bool = False) -> None:
        return self._list(
            "list", {k for k, v in {}.items() if v is not None}, {}, all_pages
        )

    def update(
        self, id: str | None = None, body: CreateGizmoInput | None = None
    ) -> None:
        return self._call(
            "update",
            {k for k, v in {"id": id, "body": body}.items() if v is not None},
            {"id": id, "body": body},
        )


class ThingResource(_ResourceBase):
    """Typed wrapper for ``thing`` (backed by ``ThingsApi``; id param is ``thing_id``)."""

    _bindings: ClassVar[dict[str, list[dict[str, Any]]]] = {
        "delete": [
            {
                "raw_method": "delete_thing",
                "serialize_name": "_delete_thing_serialize",
                "requires": ["thing_id"],
                "param_map": {"thing_id": "thing_id"},
                "body": None,
                "enums": {},
            }
        ],
        "get": [
            {
                "raw_method": "get_thing",
                "serialize_name": "_get_thing_serialize",
                "requires": ["thing_id"],
                "param_map": {"thing_id": "thing_id"},
                "body": None,
                "enums": {},
            }
        ],
    }

    def __init__(self, api: ThingsApi) -> None:
        self._api = api

    def delete(self, thing_id: str | None = None) -> None:
        return self._call(
            "delete",
            {k for k, v in {"thing_id": thing_id}.items() if v is not None},
            {"thing_id": thing_id},
        )

    def get(self, thing_id: str | None = None) -> None:
        return self._fetch(
            "get",
            {k for k, v in {"thing_id": thing_id}.items() if v is not None},
            {"thing_id": thing_id},
        )
