from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.post_scope_device_groups import PostScopeDeviceGroups
    from ..models.post_scope_locations import PostScopeLocations
    from ..models.post_scope_private_ips import PostScopePrivateIps
    from ..models.post_scope_public_ips import PostScopePublicIps
    from ..models.post_scope_users import PostScopeUsers


T = TypeVar("T", bound="PostScope")


@_attrs_define
class PostScope:
    """Provide scope to describe this rule

    Attributes:
        users (PostScopeUsers | Unset): The users or user groups the rule applies to.
        device_groups (PostScopeDeviceGroups | Unset): The device groups the rule applies to.
        public_ips (PostScopePublicIps | Unset): The public IP addresses the rule applies to.
        private_ips (PostScopePrivateIps | Unset): The private IP addresses the rule applies to.
        locations (PostScopeLocations | Unset): The locations the rule applies to.
    """

    users: PostScopeUsers | Unset = UNSET
    device_groups: PostScopeDeviceGroups | Unset = UNSET
    public_ips: PostScopePublicIps | Unset = UNSET
    private_ips: PostScopePrivateIps | Unset = UNSET
    locations: PostScopeLocations | Unset = UNSET

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
        from ..models.post_scope_device_groups import PostScopeDeviceGroups
        from ..models.post_scope_locations import PostScopeLocations
        from ..models.post_scope_private_ips import PostScopePrivateIps
        from ..models.post_scope_public_ips import PostScopePublicIps
        from ..models.post_scope_users import PostScopeUsers

        d = dict(src_dict)
        _users = d.pop("users", UNSET)
        users: PostScopeUsers | Unset
        if isinstance(_users, Unset):
            users = UNSET
        else:
            users = PostScopeUsers.from_dict(_users)

        _device_groups = d.pop("deviceGroups", UNSET)
        device_groups: PostScopeDeviceGroups | Unset
        if isinstance(_device_groups, Unset):
            device_groups = UNSET
        else:
            device_groups = PostScopeDeviceGroups.from_dict(_device_groups)

        _public_ips = d.pop("publicIps", UNSET)
        public_ips: PostScopePublicIps | Unset
        if isinstance(_public_ips, Unset):
            public_ips = UNSET
        else:
            public_ips = PostScopePublicIps.from_dict(_public_ips)

        _private_ips = d.pop("privateIps", UNSET)
        private_ips: PostScopePrivateIps | Unset
        if isinstance(_private_ips, Unset):
            private_ips = UNSET
        else:
            private_ips = PostScopePrivateIps.from_dict(_private_ips)

        _locations = d.pop("locations", UNSET)
        locations: PostScopeLocations | Unset
        if isinstance(_locations, Unset):
            locations = UNSET
        else:
            locations = PostScopeLocations.from_dict(_locations)

        post_scope = cls(
            users=users,
            device_groups=device_groups,
            public_ips=public_ips,
            private_ips=private_ips,
            locations=locations,
        )

        return post_scope
