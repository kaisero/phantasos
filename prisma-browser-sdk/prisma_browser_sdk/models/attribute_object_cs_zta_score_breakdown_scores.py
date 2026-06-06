from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.cs_zta_score import CsZtaScore


T = TypeVar("T", bound="AttributeObjectCsZtaScoreBreakdownScores")


@_attrs_define
class AttributeObjectCsZtaScoreBreakdownScores:
    """Breakdown scores with separate OS and sensor score ranges for granular validation.

    Attributes:
        os_score (CsZtaScore):
        sensor_score (CsZtaScore):
    """

    os_score: CsZtaScore
    sensor_score: CsZtaScore
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        os_score = self.os_score.to_dict()

        sensor_score = self.sensor_score.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "osScore": os_score,
                "sensorScore": sensor_score,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.cs_zta_score import CsZtaScore

        d = dict(src_dict)
        os_score = CsZtaScore.from_dict(d.pop("osScore"))

        sensor_score = CsZtaScore.from_dict(d.pop("sensorScore"))

        attribute_object_cs_zta_score_breakdown_scores = cls(
            os_score=os_score,
            sensor_score=sensor_score,
        )

        attribute_object_cs_zta_score_breakdown_scores.additional_properties = d
        return attribute_object_cs_zta_score_breakdown_scores

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
