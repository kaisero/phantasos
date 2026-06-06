from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.system_integrity_posture_status import SystemIntegrityPostureStatus

if TYPE_CHECKING:
    from ..models.system_integrity_posture_services import SystemIntegrityPostureServices


T = TypeVar("T", bound="SystemIntegrityPosture")


@_attrs_define
class SystemIntegrityPosture:
    """
    Attributes:
        status (SystemIntegrityPostureStatus): System integrity status
        services (SystemIntegrityPostureServices):
    """

    status: SystemIntegrityPostureStatus
    services: SystemIntegrityPostureServices
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status = self.status.value

        services = self.services.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "status": status,
                "services": services,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.system_integrity_posture_services import SystemIntegrityPostureServices

        d = dict(src_dict)
        status = SystemIntegrityPostureStatus(d.pop("status"))

        services = SystemIntegrityPostureServices.from_dict(d.pop("services"))

        system_integrity_posture = cls(
            status=status,
            services=services,
        )

        system_integrity_posture.additional_properties = d
        return system_integrity_posture

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
