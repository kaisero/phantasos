from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.policy_positioning_target_position import PolicyPositioningTargetPosition
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.policy_positioning_target_anchor import PolicyPositioningTargetAnchor


T = TypeVar("T", bound="PolicyPositioningTarget")


@_attrs_define
class PolicyPositioningTarget:
    """
    Attributes:
        position (PolicyPositioningTargetPosition): Where to place the entity: top (first), bottom (last), before (above
            anchor), after (below anchor). The before and after values require the anchor field. The top and bottom values
            must not include an anchor field — providing an anchor with top or bottom is a validation error.
        anchor (PolicyPositioningTargetAnchor | Unset):
        section_id (None | str | Unset): The section the rule should belong to. Only valid for rule POST and PATCH; must
            be null/omitted for section POST and PATCH (sections cannot be nested). The anchor (if any) must reside in this
            same container.
    """

    position: PolicyPositioningTargetPosition
    anchor: PolicyPositioningTargetAnchor | Unset = UNSET
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
        from ..models.policy_positioning_target_anchor import PolicyPositioningTargetAnchor

        d = dict(src_dict)
        position = PolicyPositioningTargetPosition(d.pop("position"))

        _anchor = d.pop("anchor", UNSET)
        anchor: PolicyPositioningTargetAnchor | Unset
        if isinstance(_anchor, Unset):
            anchor = UNSET
        else:
            anchor = PolicyPositioningTargetAnchor.from_dict(_anchor)

        def _parse_section_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        section_id = _parse_section_id(d.pop("sectionId", UNSET))

        policy_positioning_target = cls(
            position=position,
            anchor=anchor,
            section_id=section_id,
        )

        return policy_positioning_target
