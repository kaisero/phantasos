from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.rule_mode import RuleMode
from ..models.sign_in_rule_action import SignInRuleAction
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.policy_positioning import PolicyPositioning
    from ..models.post_scope import PostScope


T = TypeVar("T", bound="CreateSignInRuleBody")


@_attrs_define
class CreateSignInRuleBody:
    """
    Attributes:
        name (str): The name or title of the rule.
        mode (RuleMode): The mode of the rule.
        action (SignInRuleAction): Provide action to describe this rule
        description (str | Unset): The detailed description of the rule.
        scope (PostScope | Unset): Provide scope to describe this rule
        positioning (PolicyPositioning | Unset): Optional placement directive for the entity. On create, when omitted,
            the entity is placed at the top of the stack. On update, when omitted, the entity's current position is
            preserved.
    """

    name: str
    mode: RuleMode
    action: SignInRuleAction
    description: str | Unset = UNSET
    scope: PostScope | Unset = UNSET
    positioning: PolicyPositioning | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        mode = self.mode.value

        action = self.action.value

        description = self.description

        scope: dict[str, Any] | Unset = UNSET
        if not isinstance(self.scope, Unset):
            scope = self.scope.to_dict()

        positioning: dict[str, Any] | Unset = UNSET
        if not isinstance(self.positioning, Unset):
            positioning = self.positioning.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "mode": mode,
                "action": action,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if scope is not UNSET:
            field_dict["scope"] = scope
        if positioning is not UNSET:
            field_dict["positioning"] = positioning

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.policy_positioning import PolicyPositioning
        from ..models.post_scope import PostScope

        d = dict(src_dict)
        name = d.pop("name")

        mode = RuleMode(d.pop("mode"))

        action = SignInRuleAction(d.pop("action"))

        description = d.pop("description", UNSET)

        _scope = d.pop("scope", UNSET)
        scope: PostScope | Unset
        if isinstance(_scope, Unset):
            scope = UNSET
        else:
            scope = PostScope.from_dict(_scope)

        _positioning = d.pop("positioning", UNSET)
        positioning: PolicyPositioning | Unset
        if isinstance(_positioning, Unset):
            positioning = UNSET
        else:
            positioning = PolicyPositioning.from_dict(_positioning)

        create_sign_in_rule_body = cls(
            name=name,
            mode=mode,
            action=action,
            description=description,
            scope=scope,
            positioning=positioning,
        )

        return create_sign_in_rule_body
