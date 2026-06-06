from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.position_item_rule import PositionItemRule
    from ..models.position_item_section import PositionItemSection


T = TypeVar("T", bound="UpdateSecurityPositionsBody")


@_attrs_define
class UpdateSecurityPositionsBody:
    """
    Attributes:
        positions (list[PositionItemRule | PositionItemSection]): Ordered list of all rules and sections. Array index
            determines position.
    """

    positions: list[PositionItemRule | PositionItemSection]

    def to_dict(self) -> dict[str, Any]:
        from ..models.position_item_section import PositionItemSection

        positions = []
        for positions_item_data in self.positions:
            positions_item: dict[str, Any]
            if isinstance(positions_item_data, PositionItemSection):
                positions_item = positions_item_data.to_dict()
            else:
                positions_item = positions_item_data.to_dict()

            positions.append(positions_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "positions": positions,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.position_item_rule import PositionItemRule
        from ..models.position_item_section import PositionItemSection

        d = dict(src_dict)
        positions = []
        _positions = d.pop("positions")
        for positions_item_data in _positions:

            def _parse_positions_item(data: object) -> PositionItemRule | PositionItemSection:
                try:
                    if not isinstance(data, dict):
                        raise TypeError()
                    componentsschemas_position_item_type_0 = PositionItemSection.from_dict(data)

                    return componentsschemas_position_item_type_0
                except (TypeError, ValueError, AttributeError, KeyError):
                    pass
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_position_item_type_1 = PositionItemRule.from_dict(data)

                return componentsschemas_position_item_type_1

            positions_item = _parse_positions_item(positions_item_data)

            positions.append(positions_item)

        update_security_positions_body = cls(
            positions=positions,
        )

        return update_security_positions_body
