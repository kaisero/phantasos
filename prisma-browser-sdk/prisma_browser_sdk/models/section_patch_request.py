from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="SectionPatchRequest")


@_attrs_define
class SectionPatchRequest:
    """
    Attributes:
        name (str | Unset): The updated section name. Leading and trailing whitespace is trimmed before the value is
            stored. Names that are empty or consist entirely of whitespace are rejected with a 400 error.
    """

    name: str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        name = self.name

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name", UNSET)

        section_patch_request = cls(
            name=name,
        )

        return section_patch_request
