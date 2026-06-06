from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="PositionsSuccessResponse")


@_attrs_define
class PositionsSuccessResponse:
    """Successful position update response

    Attributes:
        message (str): Human-readable success message
        items_updated (int): Number of items repositioned
    """

    message: str
    items_updated: int

    def to_dict(self) -> dict[str, Any]:
        message = self.message

        items_updated = self.items_updated

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "message": message,
                "itemsUpdated": items_updated,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        message = d.pop("message")

        items_updated = d.pop("itemsUpdated")

        positions_success_response = cls(
            message=message,
            items_updated=items_updated,
        )

        return positions_success_response
