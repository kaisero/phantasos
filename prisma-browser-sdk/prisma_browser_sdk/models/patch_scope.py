from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.patch_scope_device_groups import PatchScopeDeviceGroups
    from ..models.patch_scope_locations import PatchScopeLocations
    from ..models.patch_scope_private_ips import PatchScopePrivateIps
    from ..models.patch_scope_public_ips import PatchScopePublicIps
    from ..models.patch_scope_users import PatchScopeUsers


T = TypeVar("T", bound="PatchScope")


@_attrs_define
class PatchScope:
    """Provide scope to describe this rule

    Attributes:
        users (PatchScopeUsers | Unset): The users or user groups the rule applies to.
        device_groups (PatchScopeDeviceGroups | Unset): The device groups the rule applies to.
        public_ips (PatchScopePublicIps | Unset): The public IP addresses the rule applies to.
        private_ips (PatchScopePrivateIps | Unset): The private IP addresses the rule applies to.
        locations (PatchScopeLocations | Unset): The locations the rule applies to.
    """

    users: PatchScopeUsers | Unset = UNSET
    device_groups: PatchScopeDeviceGroups | Unset = UNSET
    public_ips: PatchScopePublicIps | Unset = UNSET
    private_ips: PatchScopePrivateIps | Unset = UNSET
    locations: PatchScopeLocations | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        users: dict[str, Any] | Unset = UNSET
        if not isinstance(self.users, Unset):
            users = self.users.to_dict()

        device_groups: dict[str, Any] | Unset = UNSET
        if not isinstance(self.device_groups, Unset):
            device_groups = self.device_groups.to_dict()

        public_ips: dict[str, Any] | Unset = UNSET
        if not isinstance(self.public_ips, Unset):
            public_ips = self.public_ips.to_dict()

        private_ips: dict[str, Any] | Unset = UNSET
        if not isinstance(self.private_ips, Unset):
            private_ips = self.private_ips.to_dict()

        locations: dict[str, Any] | Unset = UNSET
        if not isinstance(self.locations, Unset):
            locations = self.locations.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if users is not UNSET:
            field_dict["users"] = users
        if device_groups is not UNSET:
            field_dict["deviceGroups"] = device_groups
        if public_ips is not UNSET:
            field_dict["publicIps"] = public_ips
        if private_ips is not UNSET:
            field_dict["privateIps"] = private_ips
        if locations is not UNSET:
            field_dict["locations"] = locations

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.patch_scope_device_groups import PatchScopeDeviceGroups
        from ..models.patch_scope_locations import PatchScopeLocations
        from ..models.patch_scope_private_ips import PatchScopePrivateIps
        from ..models.patch_scope_public_ips import PatchScopePublicIps
        from ..models.patch_scope_users import PatchScopeUsers

        d = dict(src_dict)
        _users = d.pop("users", UNSET)
        users: PatchScopeUsers | Unset
        if isinstance(_users, Unset):
            users = UNSET
        else:
            users = PatchScopeUsers.from_dict(_users)

        _device_groups = d.pop("deviceGroups", UNSET)
        device_groups: PatchScopeDeviceGroups | Unset
        if isinstance(_device_groups, Unset):
            device_groups = UNSET
        else:
            device_groups = PatchScopeDeviceGroups.from_dict(_device_groups)

        _public_ips = d.pop("publicIps", UNSET)
        public_ips: PatchScopePublicIps | Unset
        if isinstance(_public_ips, Unset):
            public_ips = UNSET
        else:
            public_ips = PatchScopePublicIps.from_dict(_public_ips)

        _private_ips = d.pop("privateIps", UNSET)
        private_ips: PatchScopePrivateIps | Unset
        if isinstance(_private_ips, Unset):
            private_ips = UNSET
        else:
            private_ips = PatchScopePrivateIps.from_dict(_private_ips)

        _locations = d.pop("locations", UNSET)
        locations: PatchScopeLocations | Unset
        if isinstance(_locations, Unset):
            locations = UNSET
        else:
            locations = PatchScopeLocations.from_dict(_locations)

        patch_scope = cls(
            users=users,
            device_groups=device_groups,
            public_ips=public_ips,
            private_ips=private_ips,
            locations=locations,
        )

        return patch_scope
