from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0


T = TypeVar("T", bound="Metadata")


@_attrs_define
class Metadata:
    """
    Attributes:
        created_time (datetime.datetime): Creation time
        last_updated_time (datetime.datetime): Last update time
        created_by (str | Unset): Created by user
        last_updated_by (str | Unset): Updated by user
        configuration_version (MetadataConfigurationVersionType0 | None | Unset): Configuration version information
    """

    created_time: datetime.datetime
    last_updated_time: datetime.datetime
    created_by: str | Unset = UNSET
    last_updated_by: str | Unset = UNSET
    configuration_version: MetadataConfigurationVersionType0 | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0

        created_time = self.created_time.isoformat()

        last_updated_time = self.last_updated_time.isoformat()

        created_by = self.created_by

        last_updated_by = self.last_updated_by

        configuration_version: dict[str, Any] | None | Unset
        if isinstance(self.configuration_version, Unset):
            configuration_version = UNSET
        elif isinstance(self.configuration_version, MetadataConfigurationVersionType0):
            configuration_version = self.configuration_version.to_dict()
        else:
            configuration_version = self.configuration_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "createdTime": created_time,
                "lastUpdatedTime": last_updated_time,
            }
        )
        if created_by is not UNSET:
            field_dict["createdBy"] = created_by
        if last_updated_by is not UNSET:
            field_dict["lastUpdatedBy"] = last_updated_by
        if configuration_version is not UNSET:
            field_dict["configurationVersion"] = configuration_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0

        d = dict(src_dict)
        created_time = datetime.datetime.fromisoformat(d.pop("createdTime"))

        last_updated_time = datetime.datetime.fromisoformat(d.pop("lastUpdatedTime"))

        created_by = d.pop("createdBy", UNSET)

        last_updated_by = d.pop("lastUpdatedBy", UNSET)

        def _parse_configuration_version(data: object) -> MetadataConfigurationVersionType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                componentsschemas_metadata_configuration_version_type_0 = MetadataConfigurationVersionType0.from_dict(
                    data
                )

                return componentsschemas_metadata_configuration_version_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(MetadataConfigurationVersionType0 | None | Unset, data)

        configuration_version = _parse_configuration_version(d.pop("configurationVersion", UNSET))

        metadata = cls(
            created_time=created_time,
            last_updated_time=last_updated_time,
            created_by=created_by,
            last_updated_by=last_updated_by,
            configuration_version=configuration_version,
        )

        metadata.additional_properties = d
        return metadata

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
