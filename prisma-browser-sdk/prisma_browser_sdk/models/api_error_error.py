from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define

from ..models.api_error_error_code import ApiErrorErrorCode
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.api_error_error_details_item import ApiErrorErrorDetailsItem


T = TypeVar("T", bound="ApiErrorError")


@_attrs_define
class ApiErrorError:
    """
    Attributes:
        code (ApiErrorErrorCode): Machine-readable error code
        message (str): Human-readable error message
        timestamp (datetime.datetime): When the error occurred
        details (list[ApiErrorErrorDetailsItem] | Unset): Detailed error information
    """

    code: ApiErrorErrorCode
    message: str
    timestamp: datetime.datetime
    details: list[ApiErrorErrorDetailsItem] | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        code = self.code.value

        message = self.message

        timestamp = self.timestamp.isoformat()

        details: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.details, Unset):
            details = []
            for details_item_data in self.details:
                details_item = details_item_data.to_dict()
                details.append(details_item)

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "code": code,
                "message": message,
                "timestamp": timestamp,
            }
        )
        if details is not UNSET:
            field_dict["details"] = details

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.api_error_error_details_item import ApiErrorErrorDetailsItem

        d = dict(src_dict)
        code = ApiErrorErrorCode(d.pop("code"))

        message = d.pop("message")

        timestamp = datetime.datetime.fromisoformat(d.pop("timestamp"))

        _details = d.pop("details", UNSET)
        details: list[ApiErrorErrorDetailsItem] | Unset = UNSET
        if _details is not UNSET:
            details = []
            for details_item_data in _details:
                details_item = ApiErrorErrorDetailsItem.from_dict(details_item_data)

                details.append(details_item)

        api_error_error = cls(
            code=code,
            message=message,
            timestamp=timestamp,
            details=details,
        )

        return api_error_error
