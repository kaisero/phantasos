from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.rule_mode import RuleMode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.post_scope import PostScope


T = TypeVar("T", bound="BasePostRuleRequest")


@_attrs_define
class BasePostRuleRequest:
    """
    Attributes:
        name (str): The name or title of the rule.
        mode (RuleMode): The mode of the rule.
        description (str | Unset): The detailed description of the rule.
        scope (PostScope | Unset): Provide scope to describe this rule
    """

    name: str
    mode: RuleMode
    description: str | Unset = UNSET
    scope: PostScope | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        mode = self.mode.value

        description = self.description

        scope: dict[str, Any] | Unset = UNSET
        if not isinstance(self.scope, Unset):
            scope = self.scope.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "mode": mode,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if scope is not UNSET:
            field_dict["scope"] = scope

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.post_scope import PostScope

        d = dict(src_dict)
        name = d.pop("name")

        mode = RuleMode(d.pop("mode"))

        description = d.pop("description", UNSET)

        _scope = d.pop("scope", UNSET)
        scope: PostScope | Unset
        if isinstance(_scope, Unset):
            scope = UNSET
        else:
            scope = PostScope.from_dict(_scope)

        base_post_rule_request = cls(
            name=name,
            mode=mode,
            description=description,
            scope=scope,
        )

        return base_post_rule_request
