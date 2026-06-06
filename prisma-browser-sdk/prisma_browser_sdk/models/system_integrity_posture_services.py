from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="SystemIntegrityPostureServices")


@_attrs_define
class SystemIntegrityPostureServices:
    """
    Attributes:
        drivers_signing_enforcement (bool | Unset):
        kernel_debugger (bool | Unset):
        secure_boot (bool | Unset):
        sip (bool | Unset):
        gatekeeper (bool | Unset):
    """

    drivers_signing_enforcement: bool | Unset = UNSET
    kernel_debugger: bool | Unset = UNSET
    secure_boot: bool | Unset = UNSET
    sip: bool | Unset = UNSET
    gatekeeper: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        drivers_signing_enforcement = self.drivers_signing_enforcement

        kernel_debugger = self.kernel_debugger

        secure_boot = self.secure_boot

        sip = self.sip

        gatekeeper = self.gatekeeper

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if drivers_signing_enforcement is not UNSET:
            field_dict["driversSigningEnforcement"] = drivers_signing_enforcement
        if kernel_debugger is not UNSET:
            field_dict["kernelDebugger"] = kernel_debugger
        if secure_boot is not UNSET:
            field_dict["secureBoot"] = secure_boot
        if sip is not UNSET:
            field_dict["SIP"] = sip
        if gatekeeper is not UNSET:
            field_dict["gatekeeper"] = gatekeeper

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        drivers_signing_enforcement = d.pop("driversSigningEnforcement", UNSET)

        kernel_debugger = d.pop("kernelDebugger", UNSET)

        secure_boot = d.pop("secureBoot", UNSET)

        sip = d.pop("SIP", UNSET)

        gatekeeper = d.pop("gatekeeper", UNSET)

        system_integrity_posture_services = cls(
            drivers_signing_enforcement=drivers_signing_enforcement,
            kernel_debugger=kernel_debugger,
            secure_boot=secure_boot,
            sip=sip,
            gatekeeper=gatekeeper,
        )

        system_integrity_posture_services.additional_properties = d
        return system_integrity_posture_services

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
