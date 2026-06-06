from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..models.flush_browser_data_control_type_0_action import FlushBrowserDataControlType0Action
from ..models.flush_browser_data_control_type_0_data_types_item import FlushBrowserDataControlType0DataTypesItem
from ..models.flush_browser_data_control_type_0_trigger import FlushBrowserDataControlType0Trigger
from ..types import UNSET, Unset

T = TypeVar("T", bound="FlushBrowserDataControlType0")


@_attrs_define
class FlushBrowserDataControlType0:
    """Set temporary browser sessions, so browser data will be cleaned upon close or time period.

    Attributes:
        action (FlushBrowserDataControlType0Action): Whether Flush Browser Data is enabled.
        trigger (FlushBrowserDataControlType0Trigger | Unset): Operating mode for Flush Browser Data. Required when
            action is 'enable'.
        data_types (list[FlushBrowserDataControlType0DataTypesItem] | Unset): Browser data types to clear. At least one
            must be selected when action is 'enable'.
        interval_hours (int | Unset): Time period in hours. Required when trigger is 'timePeriod'. Applies when action
            is 'enable'.
    """

    action: FlushBrowserDataControlType0Action
    trigger: FlushBrowserDataControlType0Trigger | Unset = UNSET
    data_types: list[FlushBrowserDataControlType0DataTypesItem] | Unset = UNSET
    interval_hours: int | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action.value

        trigger: str | Unset = UNSET
        if not isinstance(self.trigger, Unset):
            trigger = self.trigger.value

        data_types: list[str] | Unset = UNSET
        if not isinstance(self.data_types, Unset):
            data_types = []
            for data_types_item_data in self.data_types:
                data_types_item = data_types_item_data.value
                data_types.append(data_types_item)

        interval_hours = self.interval_hours

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "action": action,
            }
        )
        if trigger is not UNSET:
            field_dict["trigger"] = trigger
        if data_types is not UNSET:
            field_dict["dataTypes"] = data_types
        if interval_hours is not UNSET:
            field_dict["intervalHours"] = interval_hours

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = FlushBrowserDataControlType0Action(d.pop("action"))

        _trigger = d.pop("trigger", UNSET)
        trigger: FlushBrowserDataControlType0Trigger | Unset
        if isinstance(_trigger, Unset):
            trigger = UNSET
        else:
            trigger = FlushBrowserDataControlType0Trigger(_trigger)

        _data_types = d.pop("dataTypes", UNSET)
        data_types: list[FlushBrowserDataControlType0DataTypesItem] | Unset = UNSET
        if _data_types is not UNSET:
            data_types = []
            for data_types_item_data in _data_types:
                data_types_item = FlushBrowserDataControlType0DataTypesItem(data_types_item_data)

                data_types.append(data_types_item)

        interval_hours = d.pop("intervalHours", UNSET)

        flush_browser_data_control_type_0 = cls(
            action=action,
            trigger=trigger,
            data_types=data_types,
            interval_hours=interval_hours,
        )

        return flush_browser_data_control_type_0
