from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..models.position_item_rule_type import PositionItemRuleType
from ..types import UNSET, Unset

T = TypeVar("T", bound="PositionItemRule")


@_attrs_define
class PositionItemRule:
    """A rule in the desired position order

    Attributes:
        type_ (PositionItemRuleType): Discriminator — must be "Rule"
        id (str): The rule ID
        section_id (None | str | Unset): The section this rule belongs to (null or omitted = standalone)
    """

    type_: PositionItemRuleType
    id: str
    section_id: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        type_ = self.type_.value

        id = self.id

        section_id: None | str | Unset
        if isinstance(self.section_id, Unset):
            section_id = UNSET
        else:
            section_id = self.section_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "type": type_,
                "id": id,
            }
        )
        if section_id is not UNSET:
            field_dict["sectionId"] = section_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        type_ = PositionItemRuleType(d.pop("type"))

        id = d.pop("id")

        def _parse_section_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        section_id = _parse_section_id(d.pop("sectionId", UNSET))

        position_item_rule = cls(
            type_=type_,
            id=id,
            section_id=section_id,
        )

        return position_item_rule
