from __future__ import annotations

from typing import Any

from ..api import WidgetsApi
from .resources import WidgetResource

# Raw `*Api` classes keyed by api-class attr (the `_RESOURCES` introspection target).
_RESOURCES = {
    "widgets": WidgetsApi,
}

# Object -> (wrapper class, backing `_RESOURCES` api-class attr).
_WRAPPERS = {
    "widget": (WidgetResource, "widgets"),
}


class Client:
    """Minimal sub-facade mirroring the real SDK's per-sub Client (for tests)."""

    def __init__(self, api_client: Any = None) -> None:
        self._api_client = api_client
        _apis = {attr: cls(api_client) for attr, cls in _RESOURCES.items()}
        for obj, (wrapper_cls, api_attr) in _WRAPPERS.items():
            setattr(self, obj, wrapper_cls(_apis[api_attr]))

    @classmethod
    def from_env(cls) -> Client:
        return cls()
