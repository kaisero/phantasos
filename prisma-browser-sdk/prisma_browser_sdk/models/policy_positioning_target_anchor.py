from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.policy_positioning_target_anchor_type import PolicyPositioningTargetAnchorType

T = TypeVar("T", bound="PolicyPositioningTargetAnchor")


@_attrs_define
class PolicyPositioningTargetAnchor:
    """
    Attributes:
        type_ (PolicyPositioningTargetAnchorType):
        id (str): The entity ID of the anchor item.
    """

    type_: PolicyPositioningTargetAnchorType
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
        type_ = PolicyPositioningTargetAnchorType(d.pop("type"))

        id = d.pop("id")

        policy_positioning_target_anchor = cls(
            type_=type_,
            id=id,
        )

        return policy_positioning_target_anchor
