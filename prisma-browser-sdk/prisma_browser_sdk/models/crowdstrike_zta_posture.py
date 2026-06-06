from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CrowdstrikeZTAPosture")


@_attrs_define
class CrowdstrikeZTAPosture:
    """
    Attributes:
        score (int):
        sensor_score (int):
        os_score (int):
        cid (str):
    """

    score: int
    sensor_score: int
    os_score: int
    cid: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        score = self.score

        sensor_score = self.sensor_score

        os_score = self.os_score

        cid = self.cid

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "score": score,
                "sensorScore": sensor_score,
                "osScore": os_score,
                "CID": cid,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        score = d.pop("score")

        sensor_score = d.pop("sensorScore")

        os_score = d.pop("osScore")

        cid = d.pop("CID")

        crowdstrike_zta_posture = cls(
            score=score,
            sensor_score=sensor_score,
            os_score=os_score,
            cid=cid,
        )

        crowdstrike_zta_posture.additional_properties = d
        return crowdstrike_zta_posture

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
