from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.user_group_provider import UserGroupProvider
from ..types import UNSET, Unset

T = TypeVar("T", bound="UserGroup")


@_attrs_define
class UserGroup:
    """
    Attributes:
        id (str): Unique identifier
        name (str): Name
        last_updated (datetime.datetime | Unset): Last updated
        created_at (datetime.datetime | Unset): Created at
        provider (UserGroupProvider | Unset): Provider
    """

    id: str
    name: str
    last_updated: datetime.datetime | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    provider: UserGroupProvider | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        last_updated: str | Unset = UNSET
        if not isinstance(self.last_updated, Unset):
            last_updated = self.last_updated.isoformat()

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        provider: str | Unset = UNSET
        if not isinstance(self.provider, Unset):
            provider = self.provider.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
            }
        )
        if last_updated is not UNSET:
            field_dict["lastUpdated"] = last_updated
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if provider is not UNSET:
            field_dict["provider"] = provider

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        _last_updated = d.pop("lastUpdated", UNSET)
        last_updated: datetime.datetime | Unset
        if isinstance(_last_updated, Unset):
            last_updated = UNSET
        else:
            last_updated = datetime.datetime.fromisoformat(_last_updated)

        _created_at = d.pop("createdAt", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _provider = d.pop("provider", UNSET)
        provider: UserGroupProvider | Unset
        if isinstance(_provider, Unset):
            provider = UNSET
        else:
            provider = UserGroupProvider(_provider)

        user_group = cls(
            id=id,
            name=name,
            last_updated=last_updated,
            created_at=created_at,
            provider=provider,
        )

        user_group.additional_properties = d
        return user_group

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
