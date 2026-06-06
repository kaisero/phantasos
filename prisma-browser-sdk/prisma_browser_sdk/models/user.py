from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.user_provider import UserProvider
from ..models.user_status import UserStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.user_group import UserGroup


T = TypeVar("T", bound="User")


@_attrs_define
class User:
    """
    Attributes:
        id (str): Unique identifier
        external_id (str): External identifier
        email (str): Email
        last_seen (datetime.datetime): Last seen time
        first_seen (datetime.datetime): First seen time
        name (str): Name
        profile_picture_url (str): Profile Picture URL
        deleted_time (datetime.datetime): Deleted Time
        status (UserStatus): User status
        provider (UserProvider): Provider
        device_ids (list[str] | Unset): Device IDs
        user_groups (list[UserGroup] | Unset): User Groups
    """

    id: str
    external_id: str
    email: str
    last_seen: datetime.datetime
    first_seen: datetime.datetime
    name: str
    profile_picture_url: str
    deleted_time: datetime.datetime
    status: UserStatus
    provider: UserProvider
    device_ids: list[str] | Unset = UNSET
    user_groups: list[UserGroup] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        external_id = self.external_id

        email = self.email

        last_seen = self.last_seen.isoformat()

        first_seen = self.first_seen.isoformat()

        name = self.name

        profile_picture_url = self.profile_picture_url

        deleted_time = self.deleted_time.isoformat()

        status = self.status.value

        provider = self.provider.value

        device_ids: list[str] | Unset = UNSET
        if not isinstance(self.device_ids, Unset):
            device_ids = self.device_ids

        user_groups: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.user_groups, Unset):
            user_groups = []
            for user_groups_item_data in self.user_groups:
                user_groups_item = user_groups_item_data.to_dict()
                user_groups.append(user_groups_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "externalId": external_id,
                "email": email,
                "lastSeen": last_seen,
                "firstSeen": first_seen,
                "name": name,
                "profilePictureURL": profile_picture_url,
                "deletedTime": deleted_time,
                "status": status,
                "provider": provider,
            }
        )
        if device_ids is not UNSET:
            field_dict["deviceIds"] = device_ids
        if user_groups is not UNSET:
            field_dict["userGroups"] = user_groups

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user_group import UserGroup

        d = dict(src_dict)
        id = d.pop("id")

        external_id = d.pop("externalId")

        email = d.pop("email")

        last_seen = datetime.datetime.fromisoformat(d.pop("lastSeen"))

        first_seen = datetime.datetime.fromisoformat(d.pop("firstSeen"))

        name = d.pop("name")

        profile_picture_url = d.pop("profilePictureURL")

        deleted_time = datetime.datetime.fromisoformat(d.pop("deletedTime"))

        status = UserStatus(d.pop("status"))

        provider = UserProvider(d.pop("provider"))

        device_ids = cast(list[str], d.pop("deviceIds", UNSET))

        _user_groups = d.pop("userGroups", UNSET)
        user_groups: list[UserGroup] | Unset = UNSET
        if _user_groups is not UNSET:
            user_groups = []
            for user_groups_item_data in _user_groups:
                user_groups_item = UserGroup.from_dict(user_groups_item_data)

                user_groups.append(user_groups_item)

        user = cls(
            id=id,
            external_id=external_id,
            email=email,
            last_seen=last_seen,
            first_seen=first_seen,
            name=name,
            profile_picture_url=profile_picture_url,
            deleted_time=deleted_time,
            status=status,
            provider=provider,
            device_ids=device_ids,
            user_groups=user_groups,
        )

        user.additional_properties = d
        return user

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
