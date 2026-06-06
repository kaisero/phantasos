from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

T = TypeVar("T", bound="SectionUpdateRequest")


@_attrs_define
class SectionUpdateRequest:
    """
    Attributes:
        name (str): The updated section name. Leading and trailing whitespace is trimmed before the value is stored.
            Names that are empty or consist entirely of whitespace are rejected with a 400 error.
    """

    name: str

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        section_update_request = cls(
            name=name,
        )

        return section_update_request
