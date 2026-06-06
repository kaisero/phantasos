from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.plugin_event_event_type import PluginEventEventType
from ..models.plugin_event_method import PluginEventMethod
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.plugin_event_headers_item import PluginEventHeadersItem


T = TypeVar("T", bound="PluginEvent")


@_attrs_define
class PluginEvent:
    """
    Attributes:
        event_type (PluginEventEventType):
        request_url (str | Unset):
        trigger_url (str | Unset):
        trigger_on_success (bool | Unset):
        trigger_on_fail (bool | Unset):
        method (PluginEventMethod | Unset):
        status_code (int | Unset):
        min_content_length (int | Unset):
        max_content_length (int | Unset):
        headers (list[PluginEventHeadersItem] | Unset):
    """

    event_type: PluginEventEventType
    request_url: str | Unset = UNSET
    trigger_url: str | Unset = UNSET
    trigger_on_success: bool | Unset = UNSET
    trigger_on_fail: bool | Unset = UNSET
    method: PluginEventMethod | Unset = UNSET
    status_code: int | Unset = UNSET
    min_content_length: int | Unset = UNSET
    max_content_length: int | Unset = UNSET
    headers: list[PluginEventHeadersItem] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        event_type = self.event_type.value

        request_url = self.request_url

        trigger_url = self.trigger_url

        trigger_on_success = self.trigger_on_success

        trigger_on_fail = self.trigger_on_fail

        method: str | Unset = UNSET
        if not isinstance(self.method, Unset):
            method = self.method.value

        status_code = self.status_code

        min_content_length = self.min_content_length

        max_content_length = self.max_content_length

        headers: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.headers, Unset):
            headers = []
            for headers_item_data in self.headers:
                headers_item = headers_item_data.to_dict()
                headers.append(headers_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "eventType": event_type,
            }
        )
        if request_url is not UNSET:
            field_dict["requestUrl"] = request_url
        if trigger_url is not UNSET:
            field_dict["triggerUrl"] = trigger_url
        if trigger_on_success is not UNSET:
            field_dict["triggerOnSuccess"] = trigger_on_success
        if trigger_on_fail is not UNSET:
            field_dict["triggerOnFail"] = trigger_on_fail
        if method is not UNSET:
            field_dict["method"] = method
        if status_code is not UNSET:
            field_dict["statusCode"] = status_code
        if min_content_length is not UNSET:
            field_dict["minContentLength"] = min_content_length
        if max_content_length is not UNSET:
            field_dict["maxContentLength"] = max_content_length
        if headers is not UNSET:
            field_dict["headers"] = headers

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plugin_event_headers_item import PluginEventHeadersItem

        d = dict(src_dict)
        event_type = PluginEventEventType(d.pop("eventType"))

        request_url = d.pop("requestUrl", UNSET)

        trigger_url = d.pop("triggerUrl", UNSET)

        trigger_on_success = d.pop("triggerOnSuccess", UNSET)

        trigger_on_fail = d.pop("triggerOnFail", UNSET)

        _method = d.pop("method", UNSET)
        method: PluginEventMethod | Unset
        if isinstance(_method, Unset):
            method = UNSET
        else:
            method = PluginEventMethod(_method)

        status_code = d.pop("statusCode", UNSET)

        min_content_length = d.pop("minContentLength", UNSET)

        max_content_length = d.pop("maxContentLength", UNSET)

        _headers = d.pop("headers", UNSET)
        headers: list[PluginEventHeadersItem] | Unset = UNSET
        if _headers is not UNSET:
            headers = []
            for headers_item_data in _headers:
                headers_item = PluginEventHeadersItem.from_dict(headers_item_data)

                headers.append(headers_item)

        plugin_event = cls(
            event_type=event_type,
            request_url=request_url,
            trigger_url=trigger_url,
            trigger_on_success=trigger_on_success,
            trigger_on_fail=trigger_on_fail,
            method=method,
            status_code=status_code,
            min_content_length=min_content_length,
            max_content_length=max_content_length,
            headers=headers,
        )

        plugin_event.additional_properties = d
        return plugin_event

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
