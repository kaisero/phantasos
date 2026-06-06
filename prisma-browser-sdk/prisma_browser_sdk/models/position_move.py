from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.position_move_subject import PositionMoveSubject
    from ..models.position_move_target import PositionMoveTarget


T = TypeVar("T", bound="PositionMove")


@_attrs_define
class PositionMove:
    """A single move operation — repositions one rule or section within the policy.

    Attributes:
        subject (PositionMoveSubject): The entity to be moved (rule or section).
        target (PositionMoveTarget): The destination for the move. 'position' and 'anchor' describe placement within the
            container indicated by 'sectionId'. Anchoring on a Section is only valid at top level (sectionId null/omitted)
            and refers to the whole section block.
    """

    subject: PositionMoveSubject
    target: PositionMoveTarget

    def to_dict(self) -> dict[str, Any]:
        subject = self.subject.to_dict()

        target = self.target.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "subject": subject,
                "target": target,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.position_move_subject import PositionMoveSubject
        from ..models.position_move_target import PositionMoveTarget

        d = dict(src_dict)
        subject = PositionMoveSubject.from_dict(d.pop("subject"))

        target = PositionMoveTarget.from_dict(d.pop("target"))

        position_move = cls(
            subject=subject,
            target=target,
        )

        return position_move
