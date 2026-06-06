from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.position_move_subject_type import PositionMoveSubjectType

T = TypeVar("T", bound="PositionMoveSubject")


@_attrs_define
class PositionMoveSubject:
    """The entity to be moved (rule or section).

    Attributes:
        type_ (PositionMoveSubjectType): Whether the entity being moved is a rule or a section.
        id (str): The entity ID of the subject. In draft mode this is the EntityID; otherwise it is the row ID. Must
            match the actual entity type specified in 'type'.
    """

    type_: PositionMoveSubjectType
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
        type_ = PositionMoveSubjectType(d.pop("type"))

        id = d.pop("id")

        position_move_subject = cls(
            type_=type_,
            id=id,
        )

        return position_move_subject
