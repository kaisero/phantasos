from ..api import GizmosApi, ThingsApi, WidgetsApi

_RESOURCES = {
    "widgets": WidgetsApi,
    "gizmos": GizmosApi,
    "things": ThingsApi,
}


class Client:
    """Minimal facade mirroring the real SDK's Client (for tests)."""

    def __init__(self):
        for attr, cls in _RESOURCES.items():
            setattr(self, attr, cls())

    @classmethod
    def from_env(cls):
        return cls()

    def paginate(self, list_method, **filters):
        result = list_method(**filters)
        return iter(result or [])
