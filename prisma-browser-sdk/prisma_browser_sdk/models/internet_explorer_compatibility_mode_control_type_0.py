from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

if TYPE_CHECKING:
    from ..models.internet_explorer_compatibility_site import InternetExplorerCompatibilitySite


T = TypeVar("T", bound="InternetExplorerCompatibilityModeControlType0")


@_attrs_define
class InternetExplorerCompatibilityModeControlType0:
    """Configure websites that should open using Internet Explorer compatibility mode.

    Attributes:
        sites (list[InternetExplorerCompatibilitySite] | None): Websites and document modes to use for Internet Explorer
            compatibility mode.
    """

    sites: list[InternetExplorerCompatibilitySite] | None

    def to_dict(self) -> dict[str, Any]:
        sites: list[dict[str, Any]] | None
        if isinstance(self.sites, list):
            sites = []
            for sites_type_0_item_data in self.sites:
                sites_type_0_item = sites_type_0_item_data.to_dict()
                sites.append(sites_type_0_item)

        else:
            sites = self.sites

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "sites": sites,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.internet_explorer_compatibility_site import InternetExplorerCompatibilitySite

        d = dict(src_dict)

        def _parse_sites(data: object) -> list[InternetExplorerCompatibilitySite] | None:
            if data is None:
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                sites_type_0 = []
                _sites_type_0 = data
                for sites_type_0_item_data in _sites_type_0:
                    sites_type_0_item = InternetExplorerCompatibilitySite.from_dict(sites_type_0_item_data)

                    sites_type_0.append(sites_type_0_item)

                return sites_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(list[InternetExplorerCompatibilitySite] | None, data)

        sites = _parse_sites(d.pop("sites"))

        internet_explorer_compatibility_mode_control_type_0 = cls(
            sites=sites,
        )

        return internet_explorer_compatibility_mode_control_type_0
