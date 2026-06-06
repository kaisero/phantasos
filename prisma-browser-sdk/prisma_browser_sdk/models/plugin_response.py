from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.plugin import Plugin


T = TypeVar("T", bound="PluginResponse")


@_attrs_define
class PluginResponse:
    """
    Attributes:
        id (str): Unique identifier
        create_time (datetime.datetime): Creation time of the plugin
        update_time (datetime.datetime): Last update time of the plugin
        plugin (Plugin):
        application_id (str): Application ID of the application the plugin is associated to
    """

    id: str
    create_time: datetime.datetime
    update_time: datetime.datetime
    plugin: Plugin
    application_id: str
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        create_time = self.create_time.isoformat()

        update_time = self.update_time.isoformat()

        plugin = self.plugin.to_dict()

        application_id = self.application_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "createTime": create_time,
                "updateTime": update_time,
                "plugin": plugin,
                "applicationId": application_id,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plugin import Plugin

        d = dict(src_dict)
        id = d.pop("id")

        create_time = datetime.datetime.fromisoformat(d.pop("createTime"))

        update_time = datetime.datetime.fromisoformat(d.pop("updateTime"))

        plugin = Plugin.from_dict(d.pop("plugin"))

        application_id = d.pop("applicationId")

        plugin_response = cls(
            id=id,
            create_time=create_time,
            update_time=update_time,
            plugin=plugin,
            application_id=application_id,
        )

        plugin_response.additional_properties = d
        return plugin_response

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
