from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.position_move_target_position import PositionMoveTargetPosition
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.position_move_target_anchor import PositionMoveTargetAnchor


T = TypeVar("T", bound="PositionMoveTarget")


@_attrs_define
class PositionMoveTarget:
    """The destination for the move. 'position' and 'anchor' describe placement within the container indicated by
    'sectionId'. Anchoring on a Section is only valid at top level (sectionId null/omitted) and refers to the whole
    section block.

        Attributes:
            position (PositionMoveTargetPosition): Where to place the subject within its container. 'top'/'bottom':
                first/last within the container (no anchor allowed). 'before'/'after': immediately before/after the anchor
                sibling (anchor required).
            anchor (PositionMoveTargetAnchor | Unset): Reference sibling within the same container. Required when position
                is 'before' or 'after'. Forbidden for 'top' or 'bottom'. The anchor must reside in the container indicated by
                sectionId (or at top level when sectionId is null). Default (baseline) rules cannot be used as anchors.
            section_id (None | str | Unset): The section the subject should belong to after the move. Null or omitted means
                top level. Only valid when subject.type is Rule. Must be null/omitted when subject.type is Section (sections
                cannot nest). The anchor (if any) must reside in this same container.
    """

    position: PositionMoveTargetPosition
    anchor: PositionMoveTargetAnchor | Unset = UNSET
    section_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        position = self.position.value

        anchor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.anchor, Unset):
            anchor = self.anchor.to_dict()

        section_id: None | str | Unset
        if isinstance(self.section_id, Unset):
            section_id = UNSET
        else:
            section_id = self.section_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "position": position,
            }
        )
        if anchor is not UNSET:
            field_dict["anchor"] = anchor
        if section_id is not UNSET:
            field_dict["sectionId"] = section_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.position_move_target_anchor import PositionMoveTargetAnchor

        d = dict(src_dict)
        position = PositionMoveTargetPosition(d.pop("position"))

        _anchor = d.pop("anchor", UNSET)
        anchor: PositionMoveTargetAnchor | Unset
        if isinstance(_anchor, Unset):
            anchor = UNSET
        else:
            anchor = PositionMoveTargetAnchor.from_dict(_anchor)

        def _parse_section_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        section_id = _parse_section_id(d.pop("sectionId", UNSET))

        position_move_target = cls(
            position=position,
            anchor=anchor,
            section_id=section_id,
        )

        return position_move_target
