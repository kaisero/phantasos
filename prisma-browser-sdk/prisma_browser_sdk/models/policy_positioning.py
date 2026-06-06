from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.policy_positioning_target import PolicyPositioningTarget


T = TypeVar("T", bound="PolicyPositioning")


@_attrs_define
class PolicyPositioning:
    """Optional placement directive for the entity. On create, when omitted, the entity is placed at the top of the stack.
    On update, when omitted, the entity's current position is preserved.

        Attributes:
            target (PolicyPositioningTarget):
    """

    target: PolicyPositioningTarget

    def to_dict(self) -> dict[str, Any]:
        target = self.target.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "target": target,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.policy_positioning_target import PolicyPositioningTarget

        d = dict(src_dict)
        target = PolicyPositioningTarget.from_dict(d.pop("target"))

        policy_positioning = cls(
            target=target,
        )

        return policy_positioning
