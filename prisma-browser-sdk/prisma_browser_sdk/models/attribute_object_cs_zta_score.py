from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.cs_zta_basic_score_level import CsZtaBasicScoreLevel
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.attribute_object_cs_zta_score_breakdown_scores import AttributeObjectCsZtaScoreBreakdownScores
    from ..models.cs_zta_score import CsZtaScore


T = TypeVar("T", bound="AttributeObjectCsZtaScore")


@_attrs_define
class AttributeObjectCsZtaScore:
    """Check if the device meets minimum CrowdStrike Zero Trust Assessment score requirements.
    If multiple score types are provided (basicScore, overallScore, breakdownScores), the latest one will be used.

        Attributes:
            enabled (bool):
            negate (bool | Unset):  Default: False.
            basic_score (CsZtaBasicScoreLevel | Unset): Predefined basic ZTA score levels
            overall_score (CsZtaScore | Unset):
            breakdown_scores (AttributeObjectCsZtaScoreBreakdownScores | Unset): Breakdown scores with separate OS and
                sensor score ranges for granular validation.
            customer_ids (list[str] | Unset): CrowdStrike customer IDs to validate
    """

    enabled: bool
    negate: bool | Unset = False
    basic_score: CsZtaBasicScoreLevel | Unset = UNSET
    overall_score: CsZtaScore | Unset = UNSET
    breakdown_scores: AttributeObjectCsZtaScoreBreakdownScores | Unset = UNSET
    customer_ids: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        enabled = self.enabled

        negate = self.negate

        basic_score: str | Unset = UNSET
        if not isinstance(self.basic_score, Unset):
            basic_score = self.basic_score.value

        overall_score: dict[str, Any] | Unset = UNSET
        if not isinstance(self.overall_score, Unset):
            overall_score = self.overall_score.to_dict()

        breakdown_scores: dict[str, Any] | Unset = UNSET
        if not isinstance(self.breakdown_scores, Unset):
            breakdown_scores = self.breakdown_scores.to_dict()

        customer_ids: list[str] | Unset = UNSET
        if not isinstance(self.customer_ids, Unset):
            customer_ids = self.customer_ids

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "enabled": enabled,
            }
        )
        if negate is not UNSET:
            field_dict["negate"] = negate
        if basic_score is not UNSET:
            field_dict["basicScore"] = basic_score
        if overall_score is not UNSET:
            field_dict["overallScore"] = overall_score
        if breakdown_scores is not UNSET:
            field_dict["breakdownScores"] = breakdown_scores
        if customer_ids is not UNSET:
            field_dict["customerIds"] = customer_ids

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.attribute_object_cs_zta_score_breakdown_scores import AttributeObjectCsZtaScoreBreakdownScores
        from ..models.cs_zta_score import CsZtaScore

        d = dict(src_dict)
        enabled = d.pop("enabled")

        negate = d.pop("negate", UNSET)

        _basic_score = d.pop("basicScore", UNSET)
        basic_score: CsZtaBasicScoreLevel | Unset
        if isinstance(_basic_score, Unset):
            basic_score = UNSET
        else:
            basic_score = CsZtaBasicScoreLevel(_basic_score)

        _overall_score = d.pop("overallScore", UNSET)
        overall_score: CsZtaScore | Unset
        if isinstance(_overall_score, Unset):
            overall_score = UNSET
        else:
            overall_score = CsZtaScore.from_dict(_overall_score)

        _breakdown_scores = d.pop("breakdownScores", UNSET)
        breakdown_scores: AttributeObjectCsZtaScoreBreakdownScores | Unset
        if isinstance(_breakdown_scores, Unset):
            breakdown_scores = UNSET
        else:
            breakdown_scores = AttributeObjectCsZtaScoreBreakdownScores.from_dict(_breakdown_scores)

        customer_ids = cast(list[str], d.pop("customerIds", UNSET))

        attribute_object_cs_zta_score = cls(
            enabled=enabled,
            negate=negate,
            basic_score=basic_score,
            overall_score=overall_score,
            breakdown_scores=breakdown_scores,
            customer_ids=customer_ids,
        )

        attribute_object_cs_zta_score.additional_properties = d
        return attribute_object_cs_zta_score

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
