from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.get_scope_device_groups import GetScopeDeviceGroups
    from ..models.get_scope_locations import GetScopeLocations
    from ..models.get_scope_private_ips import GetScopePrivateIps
    from ..models.get_scope_public_ips import GetScopePublicIps
    from ..models.get_scope_users import GetScopeUsers


T = TypeVar("T", bound="GetScope")


@_attrs_define
class GetScope:
    """
    Attributes:
        users (GetScopeUsers): The users or user groups the rule applies to.
        device_groups (GetScopeDeviceGroups): The device groups the rule applies to.
        public_ips (GetScopePublicIps): The public IP addresses the rule applies to.
        private_ips (GetScopePrivateIps): The private IP addresses the rule applies to.
        locations (GetScopeLocations): The locations the rule applies to.
    """

    users: GetScopeUsers
    device_groups: GetScopeDeviceGroups
    public_ips: GetScopePublicIps
    private_ips: GetScopePrivateIps
    locations: GetScopeLocations
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        users = self.users.to_dict()

        device_groups = self.device_groups.to_dict()

        public_ips = self.public_ips.to_dict()

        private_ips = self.private_ips.to_dict()

        locations = self.locations.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "users": users,
                "deviceGroups": device_groups,
                "publicIps": public_ips,
                "privateIps": private_ips,
                "locations": locations,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.get_scope_device_groups import GetScopeDeviceGroups
        from ..models.get_scope_locations import GetScopeLocations
        from ..models.get_scope_private_ips import GetScopePrivateIps
        from ..models.get_scope_public_ips import GetScopePublicIps
        from ..models.get_scope_users import GetScopeUsers

        d = dict(src_dict)
        users = GetScopeUsers.from_dict(d.pop("users"))

        device_groups = GetScopeDeviceGroups.from_dict(d.pop("deviceGroups"))

        public_ips = GetScopePublicIps.from_dict(d.pop("publicIps"))

        private_ips = GetScopePrivateIps.from_dict(d.pop("privateIps"))

        locations = GetScopeLocations.from_dict(d.pop("locations"))

        get_scope = cls(
            users=users,
            device_groups=device_groups,
            public_ips=public_ips,
            private_ips=private_ips,
            locations=locations,
        )

        get_scope.additional_properties = d
        return get_scope

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
