from __future__ import annotations

from typing import Annotated

from pydantic import Field

from .models import (
    CreateGizmoInput,
    CreateWidget201Response,
    Widget,
    WidgetInput,
    WidgetList,
    WidgetType,
)


class WidgetsApi:
    def __init__(self, api_client=None):
        pass

    def create_widget(self, widget_input: WidgetInput) -> CreateWidget201Response:
        """Create a widget.

        Adds a new widget to the system.
        """

    def get_widget_by_id(
        self,
        id: Annotated[str, Field(description="The widget id.")],
        configuration_version: str | None = None,
    ) -> Widget:
        """Get a widget by id."""

    def list_widgets(
        self, name: str | None = None, limit: int | None = None
    ) -> WidgetList:
        """List widgets."""

    def delete_widget_by_id(self, id: str):
        """Delete a widget."""

    def patch_widget(self, id: str, widget_input: WidgetInput) -> Widget:
        """Patch a widget."""

    def update_widget(self, id: str, widget_input: WidgetInput) -> Widget:
        """Replace a widget (PUT)."""

    def update_widget_positions(self, body: dict):
        """Reorder widgets."""

    def suspend_widget(self, widget_input: WidgetInput):
        """Suspend widgets (body-only action)."""

    def revoke_widget(self, id: str, widget_input: WidgetInput):
        """Revoke a widget grant (id + body action)."""

    # excluded by introspection:
    def create_widget_with_http_info(self, widget_input: WidgetInput):
        ...

    def _create_widget_serialize(self, widget_input):
        ...


class GizmosApi:
    def __init__(self, api_client=None):
        pass

    def create_gizmo(self, type: WidgetType, create_gizmo_input: CreateGizmoInput):
        """Create a gizmo."""

    def get_gizmo_by_type_and_id(self, type: WidgetType, id: str):
        """Get a gizmo."""

    def list_gizmos(self):
        """List gizmos."""

    def patch_gizmo(self, id: str, create_gizmo_input: CreateGizmoInput):
        """Patch a gizmo."""

    def delete_gizmo_by_id(self, id: str):
        """Delete a gizmo."""


class ThingsApi:
    def __init__(self, api_client=None):
        pass

    def get_thing(self, thing_id: str):
        """Get a thing (id param is not literally 'id')."""

    def delete_thing(self, thing_id: str):
        """Delete a thing."""
