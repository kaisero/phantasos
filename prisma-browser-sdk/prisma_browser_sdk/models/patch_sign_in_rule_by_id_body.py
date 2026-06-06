from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.rule_mode import RuleMode
from ..models.sign_in_rule_action import SignInRuleAction
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.patch_scope import PatchScope


T = TypeVar("T", bound="PatchSignInRuleByIDBody")


@_attrs_define
class PatchSignInRuleByIDBody:
    """
    Attributes:
        name (str | Unset): The name or title of the rule.
        description (str | Unset): The detailed description of the rule.
        mode (RuleMode | Unset): The mode of the rule.
        scope (PatchScope | Unset): Provide scope to describe this rule
        action (SignInRuleAction | Unset): Provide action to describe this rule
    """

    name: str | Unset = UNSET
    description: str | Unset = UNSET
    mode: RuleMode | Unset = UNSET
    scope: PatchScope | Unset = UNSET
    action: SignInRuleAction | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        description = self.description

        mode: str | Unset = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        scope: dict[str, Any] | Unset = UNSET
        if not isinstance(self.scope, Unset):
            scope = self.scope.to_dict()

        action: str | Unset = UNSET
        if not isinstance(self.action, Unset):
            action = self.action.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if mode is not UNSET:
            field_dict["mode"] = mode
        if scope is not UNSET:
            field_dict["scope"] = scope
        if action is not UNSET:
            field_dict["action"] = action

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.patch_scope import PatchScope

        d = dict(src_dict)
        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        _mode = d.pop("mode", UNSET)
        mode: RuleMode | Unset
        if isinstance(_mode, Unset):
            mode = UNSET
        else:
            mode = RuleMode(_mode)

        _scope = d.pop("scope", UNSET)
        scope: PatchScope | Unset
        if isinstance(_scope, Unset):
            scope = UNSET
        else:
            scope = PatchScope.from_dict(_scope)

        _action = d.pop("action", UNSET)
        action: SignInRuleAction | Unset
        if isinstance(_action, Unset):
            action = UNSET
        else:
            action = SignInRuleAction(_action)

        patch_sign_in_rule_by_id_body = cls(
            name=name,
            description=description,
            mode=mode,
            scope=scope,
            action=action,
        )

        patch_sign_in_rule_by_id_body.additional_properties = d
        return patch_sign_in_rule_by_id_body

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
