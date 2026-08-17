from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from ..api import GizmosApi, ThingsApi, WidgetsApi
from .pagination import paginate
from .resources import GizmoResource, ThingResource, WidgetResource

# Raw `*Api` classes keyed by their api-class attr. Retained as the in-process
# introspection target (`registry_attr="_RESOURCES"`); NOT the client's public
# surface — the wrappers below are.
_RESOURCES = {
    "widgets": WidgetsApi,
    "gizmos": GizmosApi,
    "things": ThingsApi,
}

# Object -> (wrapper class, backing `_RESOURCES` api-class attr). The CLI's
# wrapper introspection keys off this map.
_WRAPPERS = {
    "widget": (WidgetResource, "widgets"),
    "gizmo": (GizmoResource, "gizmos"),
    "thing": (ThingResource, "things"),
}


class Client:
    """Minimal facade mirroring the real SDK's Client (for tests).

    Each object attribute is the typed wrapper for that object; the raw `*Api`
    instances are private (one per backing class, shared across the objects it
    backs).
    """

    def __init__(self, api_client: Any = None) -> None:
        self._api_client = api_client
        _apis = {attr: cls(api_client) for attr, cls in _RESOURCES.items()}
        for obj, (wrapper_cls, api_attr) in _WRAPPERS.items():
            setattr(self, obj, wrapper_cls(_apis[api_attr]))

    @classmethod
    def from_env(cls) -> Client:
        return cls()

    def paginate(self, list_method: Callable[..., Any], **filters: Any) -> Iterator[Any]:
        return paginate(list_method, **filters)

    @property
    def api_client(self) -> Any:
        return self._api_client
