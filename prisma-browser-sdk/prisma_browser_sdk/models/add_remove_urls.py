from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.url_input import UrlInput


T = TypeVar("T", bound="AddRemoveUrls")


@_attrs_define
class AddRemoveUrls:
    """Add or remove URLs from an application. The total URL count after modification cannot exceed 100.

    Attributes:
        add (list[UrlInput] | Unset):
        remove (list[UrlInput] | Unset):
    """

    add: list[UrlInput] | Unset = UNSET
    remove: list[UrlInput] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        add: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.add, Unset):
            add = []
            for add_item_data in self.add:
                add_item = add_item_data.to_dict()
                add.append(add_item)

        remove: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.remove, Unset):
            remove = []
            for remove_item_data in self.remove:
                remove_item = remove_item_data.to_dict()
                remove.append(remove_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if add is not UNSET:
            field_dict["add"] = add
        if remove is not UNSET:
            field_dict["remove"] = remove

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.url_input import UrlInput

        d = dict(src_dict)
        _add = d.pop("add", UNSET)
        add: list[UrlInput] | Unset = UNSET
        if _add is not UNSET:
            add = []
            for add_item_data in _add:
                add_item = UrlInput.from_dict(add_item_data)

                add.append(add_item)

        _remove = d.pop("remove", UNSET)
        remove: list[UrlInput] | Unset = UNSET
        if _remove is not UNSET:
            remove = []
            for remove_item_data in _remove:
                remove_item = UrlInput.from_dict(remove_item_data)

                remove.append(remove_item)

        add_remove_urls = cls(
            add=add,
            remove=remove,
        )

        add_remove_urls.additional_properties = d
        return add_remove_urls

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
