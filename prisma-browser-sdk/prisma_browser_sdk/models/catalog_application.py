from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.catalog_application_type import CatalogApplicationType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.catalog_attributes import CatalogAttributes
    from ..models.metadata import Metadata


T = TypeVar("T", bound="CatalogApplication")


@_attrs_define
class CatalogApplication:
    """Catalog Application

    Attributes:
        id (str): Unique identifier
        name (str): Name of the application
        type_ (CatalogApplicationType): Discriminator field, must be 'catalog'.
        metadata (Metadata):
        urls (list[str]): URL patterns for the application
        description (str | Unset): Description of the application
        category (str | Unset):
        catalog_name (str | Unset): The name in the application catalog
        catalog_attributes (CatalogAttributes | Unset): Catalog application attributes sourced from the Universal
            Application Directory (UAD)
    """

    id: str
    name: str
    type_: CatalogApplicationType
    metadata: Metadata
    urls: list[str]
    description: str | Unset = UNSET
    category: str | Unset = UNSET
    catalog_name: str | Unset = UNSET
    catalog_attributes: CatalogAttributes | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        type_ = self.type_.value

        metadata = self.metadata.to_dict()

        urls = self.urls

        description = self.description

        category = self.category

        catalog_name = self.catalog_name

        catalog_attributes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.catalog_attributes, Unset):
            catalog_attributes = self.catalog_attributes.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "type": type_,
                "metadata": metadata,
                "urls": urls,
            }
        )
        if description is not UNSET:
            field_dict["description"] = description
        if category is not UNSET:
            field_dict["category"] = category
        if catalog_name is not UNSET:
            field_dict["catalog_name"] = catalog_name
        if catalog_attributes is not UNSET:
            field_dict["catalog_attributes"] = catalog_attributes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.catalog_attributes import CatalogAttributes
        from ..models.metadata import Metadata

        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        type_ = CatalogApplicationType(d.pop("type"))

        metadata = Metadata.from_dict(d.pop("metadata"))

        urls = cast(list[str], d.pop("urls"))

        description = d.pop("description", UNSET)

        category = d.pop("category", UNSET)

        catalog_name = d.pop("catalog_name", UNSET)

        _catalog_attributes = d.pop("catalog_attributes", UNSET)
        catalog_attributes: CatalogAttributes | Unset
        if isinstance(_catalog_attributes, Unset):
            catalog_attributes = UNSET
        else:
            catalog_attributes = CatalogAttributes.from_dict(_catalog_attributes)

        catalog_application = cls(
            id=id,
            name=name,
            type_=type_,
            metadata=metadata,
            urls=urls,
            description=description,
            category=category,
            catalog_name=catalog_name,
            catalog_attributes=catalog_attributes,
        )

        catalog_application.additional_properties = d
        return catalog_application

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
