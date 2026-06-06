from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.user_request_remote_application import UserRequestRemoteApplication


T = TypeVar("T", bound="UserRequest")


@_attrs_define
class UserRequest:
    """
    Attributes:
        id (str): Unique identifier
        user_id (str): Request unique identifier
        type_ (str): Request type
        status (str): Request status
        url (str): bypassing url
        reason (str): reason for request
        device_id (str): Device unique identifier
        rule_id (str): Blocking rule unique identifier
        created_at (datetime.datetime): Request created at
        admin_comment (str | Unset): Admin comment
        user_accepted_at (datetime.datetime | Unset): User accepted response at
        response_time (datetime.datetime | Unset): Admin response time
        admin_bypass_timeframe (int | Unset): The timeframe for which the approval is valid
        responded_by (str | Unset): Response by
        revoked_by (str | Unset): Revoked by
        revoked_at (datetime.datetime | Unset): Admin revoke time
        revoker_comment (str | Unset): Revoke comment
        remote_application (UserRequestRemoteApplication | Unset):
    """

    id: str
    user_id: str
    type_: str
    status: str
    url: str
    reason: str
    device_id: str
    rule_id: str
    created_at: datetime.datetime
    admin_comment: str | Unset = UNSET
    user_accepted_at: datetime.datetime | Unset = UNSET
    response_time: datetime.datetime | Unset = UNSET
    admin_bypass_timeframe: int | Unset = UNSET
    responded_by: str | Unset = UNSET
    revoked_by: str | Unset = UNSET
    revoked_at: datetime.datetime | Unset = UNSET
    revoker_comment: str | Unset = UNSET
    remote_application: UserRequestRemoteApplication | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        user_id = self.user_id

        type_ = self.type_

        status = self.status

        url = self.url

        reason = self.reason

        device_id = self.device_id

        rule_id = self.rule_id

        created_at = self.created_at.isoformat()

        admin_comment = self.admin_comment

        user_accepted_at: str | Unset = UNSET
        if not isinstance(self.user_accepted_at, Unset):
            user_accepted_at = self.user_accepted_at.isoformat()

        response_time: str | Unset = UNSET
        if not isinstance(self.response_time, Unset):
            response_time = self.response_time.isoformat()

        admin_bypass_timeframe = self.admin_bypass_timeframe

        responded_by = self.responded_by

        revoked_by = self.revoked_by

        revoked_at: str | Unset = UNSET
        if not isinstance(self.revoked_at, Unset):
            revoked_at = self.revoked_at.isoformat()

        revoker_comment = self.revoker_comment

        remote_application: dict[str, Any] | Unset = UNSET
        if not isinstance(self.remote_application, Unset):
            remote_application = self.remote_application.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "userId": user_id,
                "type": type_,
                "status": status,
                "url": url,
                "reason": reason,
                "deviceId": device_id,
                "ruleId": rule_id,
                "createdAt": created_at,
            }
        )
        if admin_comment is not UNSET:
            field_dict["adminComment"] = admin_comment
        if user_accepted_at is not UNSET:
            field_dict["userAcceptedAt"] = user_accepted_at
        if response_time is not UNSET:
            field_dict["responseTime"] = response_time
        if admin_bypass_timeframe is not UNSET:
            field_dict["adminBypassTimeframe"] = admin_bypass_timeframe
        if responded_by is not UNSET:
            field_dict["respondedBy"] = responded_by
        if revoked_by is not UNSET:
            field_dict["revokedBy"] = revoked_by
        if revoked_at is not UNSET:
            field_dict["revokedAt"] = revoked_at
        if revoker_comment is not UNSET:
            field_dict["revokerComment"] = revoker_comment
        if remote_application is not UNSET:
            field_dict["remoteApplication"] = remote_application

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user_request_remote_application import UserRequestRemoteApplication

        d = dict(src_dict)
        id = d.pop("id")

        user_id = d.pop("userId")

        type_ = d.pop("type")

        status = d.pop("status")

        url = d.pop("url")

        reason = d.pop("reason")

        device_id = d.pop("deviceId")

        rule_id = d.pop("ruleId")

        created_at = datetime.datetime.fromisoformat(d.pop("createdAt"))

        admin_comment = d.pop("adminComment", UNSET)

        _user_accepted_at = d.pop("userAcceptedAt", UNSET)
        user_accepted_at: datetime.datetime | Unset
        if isinstance(_user_accepted_at, Unset):
            user_accepted_at = UNSET
        else:
            user_accepted_at = datetime.datetime.fromisoformat(_user_accepted_at)

        _response_time = d.pop("responseTime", UNSET)
        response_time: datetime.datetime | Unset
        if isinstance(_response_time, Unset):
            response_time = UNSET
        else:
            response_time = datetime.datetime.fromisoformat(_response_time)

        admin_bypass_timeframe = d.pop("adminBypassTimeframe", UNSET)

        responded_by = d.pop("respondedBy", UNSET)

        revoked_by = d.pop("revokedBy", UNSET)

        _revoked_at = d.pop("revokedAt", UNSET)
        revoked_at: datetime.datetime | Unset
        if isinstance(_revoked_at, Unset):
            revoked_at = UNSET
        else:
            revoked_at = datetime.datetime.fromisoformat(_revoked_at)

        revoker_comment = d.pop("revokerComment", UNSET)

        _remote_application = d.pop("remoteApplication", UNSET)
        remote_application: UserRequestRemoteApplication | Unset
        if isinstance(_remote_application, Unset):
            remote_application = UNSET
        else:
            remote_application = UserRequestRemoteApplication.from_dict(_remote_application)

        user_request = cls(
            id=id,
            user_id=user_id,
            type_=type_,
            status=status,
            url=url,
            reason=reason,
            device_id=device_id,
            rule_id=rule_id,
            created_at=created_at,
            admin_comment=admin_comment,
            user_accepted_at=user_accepted_at,
            response_time=response_time,
            admin_bypass_timeframe=admin_bypass_timeframe,
            responded_by=responded_by,
            revoked_by=revoked_by,
            revoked_at=revoked_at,
            revoker_comment=revoker_comment,
            remote_application=remote_application,
        )

        user_request.additional_properties = d
        return user_request

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
