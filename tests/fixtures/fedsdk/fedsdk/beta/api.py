from __future__ import annotations

from .models import Gadget, GadgetInput, GadgetList, Status


class GadgetsApi:
    def __init__(self, api_client=None):
        pass

    def create_gadget(self, gadget_input: GadgetInput) -> Gadget:
        """Create a gadget."""

    def get_gadget_by_id(self, id: str) -> Gadget:
        """Get a gadget by id."""

    def list_gadgets(self, limit: int | None = None) -> GadgetList:
        """List gadgets."""

    def update_gadget(self, id: str, gadget_input: GadgetInput) -> Gadget:
        """Update a gadget."""

    def delete_gadget_by_id(self, id: str) -> None:
        """Delete a gadget."""

    def compute_gadget(self, gadget_input: GadgetInput) -> Status:
        """Compute a gadget's status (a non-CRUD action)."""
