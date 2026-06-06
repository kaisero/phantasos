from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.request_action_action import RequestActionAction
from ..models.request_action_admin_bypass_timeframe import RequestActionAdminBypassTimeframe
from ..types import UNSET, Unset

T = TypeVar("T", bound="RequestAction")


@_attrs_define
class RequestAction:
    """
    Attributes:
        action (RequestActionAction): Action to perform on the request
        admin_comment (str | Unset): Admin comment on the action
        admin_bypass_timeframe (RequestActionAdminBypassTimeframe | Unset): The timeframe for which the approval is
            valid
    """

    action: RequestActionAction
    admin_comment: str | Unset = UNSET
    admin_bypass_timeframe: RequestActionAdminBypassTimeframe | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        admin_comment = self.admin_comment

        admin_bypass_timeframe: str | Unset = UNSET
        if not isinstance(self.admin_bypass_timeframe, Unset):
            admin_bypass_timeframe = self.admin_bypass_timeframe.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "action": action,
            }
        )
        if admin_comment is not UNSET:
            field_dict["adminComment"] = admin_comment
        if admin_bypass_timeframe is not UNSET:
            field_dict["adminBypassTimeframe"] = admin_bypass_timeframe

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = RequestActionAction(d.pop("action"))

        admin_comment = d.pop("adminComment", UNSET)

        _admin_bypass_timeframe = d.pop("adminBypassTimeframe", UNSET)
        admin_bypass_timeframe: RequestActionAdminBypassTimeframe | Unset
        if isinstance(_admin_bypass_timeframe, Unset):
            admin_bypass_timeframe = UNSET
        else:
            admin_bypass_timeframe = RequestActionAdminBypassTimeframe(_admin_bypass_timeframe)

        request_action = cls(
            action=action,
            admin_comment=admin_comment,
            admin_bypass_timeframe=admin_bypass_timeframe,
        )

        request_action.additional_properties = d
        return request_action

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
