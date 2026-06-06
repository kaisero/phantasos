from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.sign_in_rule_detailed_action_action import SignInRuleDetailedActionAction

T = TypeVar("T", bound="SignInRuleDetailedAction")


@_attrs_define
class SignInRuleDetailedAction:
    """
    Attributes:
        action (SignInRuleDetailedActionAction): The action performed by the rule
    """

    action: SignInRuleDetailedActionAction
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "action": action,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = SignInRuleDetailedActionAction(d.pop("action"))

        sign_in_rule_detailed_action = cls(
            action=action,
        )

        sign_in_rule_detailed_action.additional_properties = d
        return sign_in_rule_detailed_action

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
