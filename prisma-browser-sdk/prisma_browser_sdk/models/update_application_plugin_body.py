from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.plugin import Plugin


T = TypeVar("T", bound="UpdateApplicationPluginBody")


@_attrs_define
class UpdateApplicationPluginBody:
    """
    Attributes:
        plugin (Plugin):
    """

    plugin: Plugin
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        plugin = self.plugin.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "plugin": plugin,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plugin import Plugin

        d = dict(src_dict)
        plugin = Plugin.from_dict(d.pop("plugin"))

        update_application_plugin_body = cls(
            plugin=plugin,
        )

        update_application_plugin_body.additional_properties = d
        return update_application_plugin_body

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
