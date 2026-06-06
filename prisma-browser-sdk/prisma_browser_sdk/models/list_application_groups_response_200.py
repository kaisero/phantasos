from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.application_group import ApplicationGroup
    from ..models.page_info import PageInfo
    from ..models.response_metadata import ResponseMetadata


T = TypeVar("T", bound="ListApplicationGroupsResponse200")


@_attrs_define
class ListApplicationGroupsResponse200:
    """
    Attributes:
        data (list[ApplicationGroup] | Unset):
        metadata (ResponseMetadata | Unset): Response-level metadata
        page_info (PageInfo | Unset):
    """

    data: list[ApplicationGroup] | Unset = UNSET
    metadata: ResponseMetadata | Unset = UNSET
    page_info: PageInfo | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = []
            for data_item_data in self.data:
                data_item = data_item_data.to_dict()
                data.append(data_item)

        metadata: dict[str, Any] | Unset = UNSET
        if not isinstance(self.metadata, Unset):
            metadata = self.metadata.to_dict()

        page_info: dict[str, Any] | Unset = UNSET
        if not isinstance(self.page_info, Unset):
            page_info = self.page_info.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if data is not UNSET:
            field_dict["data"] = data
        if metadata is not UNSET:
            field_dict["metadata"] = metadata
        if page_info is not UNSET:
            field_dict["pageInfo"] = page_info

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.application_group import ApplicationGroup
        from ..models.page_info import PageInfo
        from ..models.response_metadata import ResponseMetadata

        d = dict(src_dict)
        _data = d.pop("data", UNSET)
        data: list[ApplicationGroup] | Unset = UNSET
        if _data is not UNSET:
            data = []
            for data_item_data in _data:
                data_item = ApplicationGroup.from_dict(data_item_data)

                data.append(data_item)

        _metadata = d.pop("metadata", UNSET)
        metadata: ResponseMetadata | Unset
        if isinstance(_metadata, Unset):
            metadata = UNSET
        else:
            metadata = ResponseMetadata.from_dict(_metadata)

        _page_info = d.pop("pageInfo", UNSET)
        page_info: PageInfo | Unset
        if isinstance(_page_info, Unset):
            page_info = UNSET
        else:
            page_info = PageInfo.from_dict(_page_info)

        list_application_groups_response_200 = cls(
            data=data,
            metadata=metadata,
            page_info=page_info,
        )

        list_application_groups_response_200.additional_properties = d
        return list_application_groups_response_200

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
