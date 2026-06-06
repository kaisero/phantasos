from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.rule_mode import RuleMode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_scope import GetScope
    from ..models.section_ref import SectionRef
    from ..models.sign_in_rule_detailed_action import SignInRuleDetailedAction
    from ..models.sign_in_rule_detailed_metadata import SignInRuleDetailedMetadata


T = TypeVar("T", bound="SignInRuleDetailed")


@_attrs_define
class SignInRuleDetailed:
    """A detailed sign-in rule object with complete configuration

    Attributes:
        id (str): Unique identifier for the rule
        name (str): User-friendly name for the rule
        priority (int): Order position of the rule in the list
        description (str): Detailed explanation of the rule's purpose
        mode (RuleMode): The mode of the rule.
        scope (GetScope):
        action (SignInRuleDetailedAction):
        metadata (SignInRuleDetailedMetadata):
        section (SectionRef | Unset): A reference to a policy section.
    """

    id: str
    name: str
    priority: int
    description: str
    mode: RuleMode
    scope: GetScope
    action: SignInRuleDetailedAction
    metadata: SignInRuleDetailedMetadata
    section: SectionRef | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        priority = self.priority

        description = self.description

        mode = self.mode.value

        scope = self.scope.to_dict()

        action = self.action.to_dict()

        metadata = self.metadata.to_dict()

        section: dict[str, Any] | Unset = UNSET
        if not isinstance(self.section, Unset):
            section = self.section.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "priority": priority,
                "description": description,
                "mode": mode,
                "scope": scope,
                "action": action,
                "metadata": metadata,
            }
        )
        if section is not UNSET:
            field_dict["section"] = section

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.get_scope import GetScope
        from ..models.section_ref import SectionRef
        from ..models.sign_in_rule_detailed_action import SignInRuleDetailedAction
        from ..models.sign_in_rule_detailed_metadata import SignInRuleDetailedMetadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        priority = d.pop("priority")

        description = d.pop("description")

        mode = RuleMode(d.pop("mode"))

        scope = GetScope.from_dict(d.pop("scope"))

        action = SignInRuleDetailedAction.from_dict(d.pop("action"))

        metadata = SignInRuleDetailedMetadata.from_dict(d.pop("metadata"))

        _section = d.pop("section", UNSET)
        section: SectionRef | Unset
        if isinstance(_section, Unset):
            section = UNSET
        else:
            section = SectionRef.from_dict(_section)

        sign_in_rule_detailed = cls(
            id=id,
            name=name,
            priority=priority,
            description=description,
            mode=mode,
            scope=scope,
            action=action,
            metadata=metadata,
            section=section,
        )

        sign_in_rule_detailed.additional_properties = d
        return sign_in_rule_detailed

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
