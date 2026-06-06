from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.rule_mode import RuleMode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.patch_scope import PatchScope


T = TypeVar("T", bound="BasePatchRuleRequest")


@_attrs_define
class BasePatchRuleRequest:
    """
    Attributes:
        name (str | Unset): The name or title of the rule.
        description (str | Unset): The detailed description of the rule.
        mode (RuleMode | Unset): The mode of the rule.
        scope (PatchScope | Unset): Provide scope to describe this rule
    """

    name: str | Unset = UNSET
    description: str | Unset = UNSET
    mode: RuleMode | Unset = UNSET
    scope: PatchScope | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        description = self.description

        mode: str | Unset = UNSET
        if not isinstance(self.mode, Unset):
            mode = self.mode.value

        scope: dict[str, Any] | Unset = UNSET
        if not isinstance(self.scope, Unset):
            scope = self.scope.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if mode is not UNSET:
            field_dict["mode"] = mode
        if scope is not UNSET:
            field_dict["scope"] = scope

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

        base_patch_rule_request = cls(
            name=name,
            description=description,
            mode=mode,
            scope=scope,
        )

        return base_patch_rule_request
