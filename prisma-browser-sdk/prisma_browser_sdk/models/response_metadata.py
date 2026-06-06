from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0


T = TypeVar("T", bound="ResponseMetadata")


@_attrs_define
class ResponseMetadata:
    """Response-level metadata

    Attributes:
        configuration_version (MetadataConfigurationVersionType0 | None | Unset): Configuration version information
    """

    configuration_version: MetadataConfigurationVersionType0 | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0

        configuration_version: dict[str, Any] | None | Unset
        if isinstance(self.configuration_version, Unset):
            configuration_version = UNSET
        elif isinstance(self.configuration_version, MetadataConfigurationVersionType0):
            configuration_version = self.configuration_version.to_dict()
        else:
            configuration_version = self.configuration_version

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if configuration_version is not UNSET:
            field_dict["configurationVersion"] = configuration_version

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.metadata_configuration_version_type_0 import MetadataConfigurationVersionType0

        d = dict(src_dict)

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

        response_metadata = cls(
            configuration_version=configuration_version,
        )

        response_metadata.additional_properties = d
        return response_metadata

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
