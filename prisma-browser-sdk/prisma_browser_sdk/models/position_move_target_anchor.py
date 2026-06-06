from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.position_move_target_anchor_type import PositionMoveTargetAnchorType

T = TypeVar("T", bound="PositionMoveTargetAnchor")


@_attrs_define
class PositionMoveTargetAnchor:
    """Reference sibling within the same container. Required when position is 'before' or 'after'. Forbidden for 'top' or
    'bottom'. The anchor must reside in the container indicated by sectionId (or at top level when sectionId is null).
    Default (baseline) rules cannot be used as anchors.

        Attributes:
            type_ (PositionMoveTargetAnchorType): Whether the anchor is a rule or a section. Section anchors are only valid
                at top level.
            id (str): The entity ID of the anchor item. Must match the actual entity type specified in 'type'.
    """

    type_: PositionMoveTargetAnchorType
    id: str

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        id = self.id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "type": type_,
                "id": id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = PositionMoveTargetAnchorType(d.pop("type"))

        id = d.pop("id")

        position_move_target_anchor = cls(
            type_=type_,
            id=id,
        )

        return position_move_target_anchor
