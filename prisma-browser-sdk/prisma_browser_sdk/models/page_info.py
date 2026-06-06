from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="PageInfo")


@_attrs_define
class PageInfo:
    """
    Attributes:
        has_next_page (bool): When paginating forwards, are there more items?
        cursor (None | str | Unset): When paginating forwards, the cursor to continue.
        total_count (int | Unset): Total number of items across all pages. Currently populated only by policy GET
            endpoints.
    """

    has_next_page: bool
    cursor: None | str | Unset = UNSET
    total_count: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        has_next_page = self.has_next_page

        cursor: None | str | Unset
        if isinstance(self.cursor, Unset):
            cursor = UNSET
        else:
            cursor = self.cursor

        total_count = self.total_count

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "hasNextPage": has_next_page,
            }
        )
        if cursor is not UNSET:
            field_dict["cursor"] = cursor
        if total_count is not UNSET:
            field_dict["totalCount"] = total_count

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        has_next_page = d.pop("hasNextPage")

        def _parse_cursor(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        cursor = _parse_cursor(d.pop("cursor", UNSET))

        total_count = d.pop("totalCount", UNSET)

        page_info = cls(
            has_next_page=has_next_page,
            cursor=cursor,
            total_count=total_count,
        )

        page_info.additional_properties = d
        return page_info

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
