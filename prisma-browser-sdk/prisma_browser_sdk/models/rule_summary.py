from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.rule_mode import RuleMode
from ..models.rule_summary_type import RuleSummaryType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.section_ref import SectionRef


T = TypeVar("T", bound="RuleSummary")


@_attrs_define
class RuleSummary:
    """A summary of a specific rule.

    Attributes:
        id (str): The unique identifier for the policy item.
        position (int): 1-based index of this item in the flat list. Example: 1.
        type_ (RuleSummaryType): Discriminator field, must be 'Rule'.
        mode (RuleMode): The mode of the rule.
        name (str | Unset): The name or title of the rule or section.
        section (SectionRef | Unset): A reference to a policy section.
        description (str | Unset): The detailed description of the rule.
        evaluation_order (int | Unset): 1-based rank of this rule counting only rules (not sections). Defines the order
            in which rules are evaluated in the policy.
    """

    id: str
    position: int
    type_: RuleSummaryType
    mode: RuleMode
    name: str | Unset = UNSET
    section: SectionRef | Unset = UNSET
    description: str | Unset = UNSET
    evaluation_order: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        position = self.position

        type_ = self.type_.value

        mode = self.mode.value

        name = self.name

        section: dict[str, Any] | Unset = UNSET
        if not isinstance(self.section, Unset):
            section = self.section.to_dict()

        description = self.description

        evaluation_order = self.evaluation_order

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "position": position,
                "type": type_,
                "mode": mode,
            }
        )
        if name is not UNSET:
            field_dict["name"] = name
        if section is not UNSET:
            field_dict["section"] = section
        if description is not UNSET:
            field_dict["description"] = description
        if evaluation_order is not UNSET:
            field_dict["evaluationOrder"] = evaluation_order

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.section_ref import SectionRef

        d = dict(src_dict)
        id = d.pop("id")

        position = d.pop("position")

        type_ = RuleSummaryType(d.pop("type"))

        mode = RuleMode(d.pop("mode"))

        name = d.pop("name", UNSET)

        _section = d.pop("section", UNSET)
        section: SectionRef | Unset
        if isinstance(_section, Unset):
            section = UNSET
        else:
            section = SectionRef.from_dict(_section)

        description = d.pop("description", UNSET)

        evaluation_order = d.pop("evaluationOrder", UNSET)

        rule_summary = cls(
            id=id,
            position=position,
            type_=type_,
            mode=mode,
            name=name,
            section=section,
            description=description,
            evaluation_order=evaluation_order,
        )

        rule_summary.additional_properties = d
        return rule_summary

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
