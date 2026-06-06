from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.catalog_application import CatalogApplication
    from ..models.custom_application import CustomApplication
    from ..models.local_desktop_application import LocalDesktopApplication
    from ..models.non_web_application import NonWebApplication
    from ..models.page_info import PageInfo
    from ..models.private_application import PrivateApplication
    from ..models.response_metadata import ResponseMetadata


T = TypeVar("T", bound="ListApplicationsByTypeResponse200")


@_attrs_define
class ListApplicationsByTypeResponse200:
    """
    Attributes:
        data (list[CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication |
            PrivateApplication] | Unset):
        metadata (ResponseMetadata | Unset): Response-level metadata
        page_info (PageInfo | Unset):
    """

    data: (
        list[CatalogApplication | CustomApplication | LocalDesktopApplication | NonWebApplication | PrivateApplication]
        | Unset
    ) = UNSET
    metadata: ResponseMetadata | Unset = UNSET
    page_info: PageInfo | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.catalog_application import CatalogApplication
        from ..models.custom_application import CustomApplication
        from ..models.non_web_application import NonWebApplication
        from ..models.private_application import PrivateApplication

        data: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = []
            for data_item_data in self.data:
                data_item: dict[str, Any]
                if isinstance(data_item_data, CustomApplication):
                    data_item = data_item_data.to_dict()
                elif isinstance(data_item_data, PrivateApplication):
                    data_item = data_item_data.to_dict()
                elif isinstance(data_item_data, NonWebApplication):
                    data_item = data_item_data.to_dict()
                elif isinstance(data_item_data, CatalogApplication):
                    data_item = data_item_data.to_dict()
                else:
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
        from ..models.catalog_application import CatalogApplication
        from ..models.custom_application import CustomApplication
        from ..models.local_desktop_application import LocalDesktopApplication
        from ..models.non_web_application import NonWebApplication
        from ..models.page_info import PageInfo
        from ..models.private_application import PrivateApplication
        from ..models.response_metadata import ResponseMetadata

        d = dict(src_dict)
        _data = d.pop("data", UNSET)
        data: (
            list[
                CatalogApplication
                | CustomApplication
                | LocalDesktopApplication
                | NonWebApplication
                | PrivateApplication
            ]
            | Unset
        ) = UNSET
        if _data is not UNSET:
            data = []
            for data_item_data in _data:

                def _parse_data_item(
                    data: object,
                ) -> (
                    CatalogApplication
                    | CustomApplication
                    | LocalDesktopApplication
                    | NonWebApplication
                    | PrivateApplication
                ):
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        componentsschemas_application_item_type_0 = CustomApplication.from_dict(data)

                        return componentsschemas_application_item_type_0
                    except (TypeError, ValueError, AttributeError, KeyError):
                        pass
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        componentsschemas_application_item_type_1 = PrivateApplication.from_dict(data)

                        return componentsschemas_application_item_type_1
                    except (TypeError, ValueError, AttributeError, KeyError):
                        pass
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        componentsschemas_application_item_type_2 = NonWebApplication.from_dict(data)

                        return componentsschemas_application_item_type_2
                    except (TypeError, ValueError, AttributeError, KeyError):
                        pass
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        componentsschemas_application_item_type_3 = CatalogApplication.from_dict(data)

                        return componentsschemas_application_item_type_3
                    except (TypeError, ValueError, AttributeError, KeyError):
                        pass
                    if not isinstance(data, dict):
                        raise TypeError()
                    componentsschemas_application_item_type_4 = LocalDesktopApplication.from_dict(data)

                    return componentsschemas_application_item_type_4

                data_item = _parse_data_item(data_item_data)

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

        list_applications_by_type_response_200 = cls(
            data=data,
            metadata=metadata,
            page_info=page_info,
        )

        list_applications_by_type_response_200.additional_properties = d
        return list_applications_by_type_response_200

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
