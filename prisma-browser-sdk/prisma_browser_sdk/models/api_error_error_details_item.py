from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ApiErrorErrorDetailsItem")


@_attrs_define
class ApiErrorErrorDetailsItem:
    """
    Attributes:
        index (int | Unset): 0-based index of the failing move in the request array
        field (str | Unset): JSON path of the offending field (e.g. target.anchor.id)
        error (str | Unset):
        value (str | Unset):
        section_id (str | Unset):
        rule_id (str | Unset):
        rule_ids (list[str] | Unset):
        missing_rules (list[str] | Unset):
        missing_sections (list[str] | Unset):
    """

    index: int | Unset = UNSET
    field: str | Unset = UNSET
    error: str | Unset = UNSET
    value: str | Unset = UNSET
    section_id: str | Unset = UNSET
    rule_id: str | Unset = UNSET
    rule_ids: list[str] | Unset = UNSET
    missing_rules: list[str] | Unset = UNSET
    missing_sections: list[str] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        index = self.index

        field = self.field

        error = self.error

        value = self.value

        section_id = self.section_id

        rule_id = self.rule_id

        rule_ids: list[str] | Unset = UNSET
        if not isinstance(self.rule_ids, Unset):
            rule_ids = self.rule_ids

        missing_rules: list[str] | Unset = UNSET
        if not isinstance(self.missing_rules, Unset):
            missing_rules = self.missing_rules

        missing_sections: list[str] | Unset = UNSET
        if not isinstance(self.missing_sections, Unset):
            missing_sections = self.missing_sections

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if index is not UNSET:
            field_dict["index"] = index
        if field is not UNSET:
            field_dict["field"] = field
        if error is not UNSET:
            field_dict["error"] = error
        if value is not UNSET:
            field_dict["value"] = value
        if section_id is not UNSET:
            field_dict["sectionId"] = section_id
        if rule_id is not UNSET:
            field_dict["ruleId"] = rule_id
        if rule_ids is not UNSET:
            field_dict["ruleIds"] = rule_ids
        if missing_rules is not UNSET:
            field_dict["missingRules"] = missing_rules
        if missing_sections is not UNSET:
            field_dict["missingSections"] = missing_sections

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        index = d.pop("index", UNSET)

        field = d.pop("field", UNSET)

        error = d.pop("error", UNSET)

        value = d.pop("value", UNSET)

        section_id = d.pop("sectionId", UNSET)

        rule_id = d.pop("ruleId", UNSET)

        rule_ids = cast(list[str], d.pop("ruleIds", UNSET))

        missing_rules = cast(list[str], d.pop("missingRules", UNSET))

        missing_sections = cast(list[str], d.pop("missingSections", UNSET))

        api_error_error_details_item = cls(
            index=index,
            field=field,
            error=error,
            value=value,
            section_id=section_id,
            rule_id=rule_id,
            rule_ids=rule_ids,
            missing_rules=missing_rules,
            missing_sections=missing_sections,
        )

        return api_error_error_details_item
