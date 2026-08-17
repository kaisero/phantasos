from __future__ import annotations

from .models import Widget, WidgetInput, WidgetList


class WidgetsApi:
    def __init__(self, api_client=None):
        pass

    def create_widget(self, widget_input: WidgetInput) -> Widget:
        """Create a widget."""

    def get_widget_by_id(self, id: str) -> Widget:
        """Get a widget by id."""

    def list_widgets(self, limit: int | None = None) -> WidgetList:
        """List widgets."""

    def update_widget(self, id: str, widget_input: WidgetInput) -> Widget:
        """Update a widget."""

    def delete_widget_by_id(self, id: str) -> None:
        """Delete a widget."""
