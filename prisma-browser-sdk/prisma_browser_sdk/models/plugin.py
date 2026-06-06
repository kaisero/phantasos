from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.plugin_element import PluginElement
    from ..models.plugin_event import PluginEvent
    from ..models.plugin_link import PluginLink


T = TypeVar("T", bound="Plugin")


@_attrs_define
class Plugin:
    """
    Attributes:
        events (list[PluginEvent] | Unset):
        links (list[PluginLink] | Unset):
        elements (list[PluginElement] | Unset):
    """

    events: list[PluginEvent] | Unset = UNSET
    links: list[PluginLink] | Unset = UNSET
    elements: list[PluginElement] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        events: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.events, Unset):
            events = []
            for events_item_data in self.events:
                events_item = events_item_data.to_dict()
                events.append(events_item)

        links: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.links, Unset):
            links = []
            for links_item_data in self.links:
                links_item = links_item_data.to_dict()
                links.append(links_item)

        elements: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.elements, Unset):
            elements = []
            for elements_item_data in self.elements:
                elements_item = elements_item_data.to_dict()
                elements.append(elements_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if events is not UNSET:
            field_dict["events"] = events
        if links is not UNSET:
            field_dict["links"] = links
        if elements is not UNSET:
            field_dict["elements"] = elements

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plugin_element import PluginElement
        from ..models.plugin_event import PluginEvent
        from ..models.plugin_link import PluginLink

        d = dict(src_dict)
        _events = d.pop("events", UNSET)
        events: list[PluginEvent] | Unset = UNSET
        if _events is not UNSET:
            events = []
            for events_item_data in _events:
                events_item = PluginEvent.from_dict(events_item_data)

                events.append(events_item)

        _links = d.pop("links", UNSET)
        links: list[PluginLink] | Unset = UNSET
        if _links is not UNSET:
            links = []
            for links_item_data in _links:
                links_item = PluginLink.from_dict(links_item_data)

                links.append(links_item)

        _elements = d.pop("elements", UNSET)
        elements: list[PluginElement] | Unset = UNSET
        if _elements is not UNSET:
            elements = []
            for elements_item_data in _elements:
                elements_item = PluginElement.from_dict(elements_item_data)

                elements.append(elements_item)

        plugin = cls(
            events=events,
            links=links,
            elements=elements,
        )

        plugin.additional_properties = d
        return plugin

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
