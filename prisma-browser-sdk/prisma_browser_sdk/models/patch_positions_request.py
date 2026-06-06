from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.position_move import PositionMove


T = TypeVar("T", bound="PatchPositionsRequest")


@_attrs_define
class PatchPositionsRequest:
    """Request body for PATCH positions — an ordered list of moves to apply atomically.

    Example:
        {'moves': [{'subject': {'type': 'Rule', 'id': '0RU00000000000000000000000001'}, 'target': {'position': 'after',
            'anchor': {'type': 'Section', 'id': '0RS00000000000000000000000001'}, 'sectionId': None}}, {'subject': {'type':
            'Section', 'id': '0RS00000000000000000000000002'}, 'target': {'position': 'top'}}]}

    Attributes:
        moves (list[PositionMove]): Ordered list of moves to apply. Each move repositions one rule or section into an
            explicit container (target.sectionId) using a position keyword plus an optional anchor. Section subjects auto-
            carry their child rules. Default (baseline) rules are pinned at the bottom and cannot be moved or anchored on.
            All moves apply atomically — if any move fails, no DB changes or audit events are produced. The failing move's
            index is in the error details.
    """

    moves: list[PositionMove]

    def to_dict(self) -> dict[str, Any]:
        moves = []
        for moves_item_data in self.moves:
            moves_item = moves_item_data.to_dict()
            moves.append(moves_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "moves": moves,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.position_move import PositionMove

        d = dict(src_dict)
        moves = []
        _moves = d.pop("moves")
        for moves_item_data in _moves:
            moves_item = PositionMove.from_dict(moves_item_data)

            moves.append(moves_item)

        patch_positions_request = cls(
            moves=moves,
        )

        return patch_positions_request
