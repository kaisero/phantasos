from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.bulk_create_applications_response_400 import BulkCreateApplicationsResponse400
from ...models.bulk_create_applications_response_409 import BulkCreateApplicationsResponse409
from ...models.bulk_create_applications_type import BulkCreateApplicationsType
from ...models.bulk_created_item import BulkCreatedItem
from ...models.custom_application_input import CustomApplicationInput
from ...models.local_desktop_application_input import LocalDesktopApplicationInput
from ...models.non_web_application_input import NonWebApplicationInput
from ...models.private_application_input import PrivateApplicationInput
from ...types import Response


def _get_kwargs(
    type_: BulkCreateApplicationsType,
    *,
    body: list[
        CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput
    ],
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/applications/bulk-create/{type_}".format(
            type_=quote(str(type_), safe=""),
        ),
    }

    _kwargs["json"] = []
    for body_item_data in body:
        body_item: dict[str, Any]
        if isinstance(body_item_data, CustomApplicationInput):
            body_item = body_item_data.to_dict()
        elif isinstance(body_item_data, PrivateApplicationInput):
            body_item = body_item_data.to_dict()
        elif isinstance(body_item_data, NonWebApplicationInput):
            body_item = body_item_data.to_dict()
        else:
            body_item = body_item_data.to_dict()

        _kwargs["json"].append(body_item)

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem] | None:
    if response.status_code == 201:
        response_201 = []
        _response_201 = response.json()
        for componentsschemas_bulk_created_response_item_data in _response_201:
            componentsschemas_bulk_created_response_item = BulkCreatedItem.from_dict(
                componentsschemas_bulk_created_response_item_data
            )

            response_201.append(componentsschemas_bulk_created_response_item)

        return response_201

    if response.status_code == 400:
        response_400 = BulkCreateApplicationsResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 409:
        response_409 = BulkCreateApplicationsResponse409.from_dict(response.json())

        return response_409

    if response.status_code == 500:
        response_500 = cast(Any, None)
        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    type_: BulkCreateApplicationsType,
    *,
    client: AuthenticatedClient | Client,
    body: list[
        CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput
    ],
) -> Response[Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]]:
    """Creates multiple applications

     Adds multiple new applications of the specified type to the management console in a single
    operation.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (BulkCreateApplicationsType):
        body (list[CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput
            | PrivateApplicationInput]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]]
    """

    kwargs = _get_kwargs(
        type_=type_,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    type_: BulkCreateApplicationsType,
    *,
    client: AuthenticatedClient | Client,
    body: list[
        CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput
    ],
) -> Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem] | None:
    """Creates multiple applications

     Adds multiple new applications of the specified type to the management console in a single
    operation.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (BulkCreateApplicationsType):
        body (list[CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput
            | PrivateApplicationInput]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]
    """

    return sync_detailed(
        type_=type_,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    type_: BulkCreateApplicationsType,
    *,
    client: AuthenticatedClient | Client,
    body: list[
        CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput
    ],
) -> Response[Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]]:
    """Creates multiple applications

     Adds multiple new applications of the specified type to the management console in a single
    operation.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (BulkCreateApplicationsType):
        body (list[CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput
            | PrivateApplicationInput]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]]
    """

    kwargs = _get_kwargs(
        type_=type_,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    type_: BulkCreateApplicationsType,
    *,
    client: AuthenticatedClient | Client,
    body: list[
        CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput
    ],
) -> Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem] | None:
    """Creates multiple applications

     Adds multiple new applications of the specified type to the management console in a single
    operation.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (BulkCreateApplicationsType):
        body (list[CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput
            | PrivateApplicationInput]):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | BulkCreateApplicationsResponse400 | BulkCreateApplicationsResponse409 | list[BulkCreatedItem]
    """

    return (
        await asyncio_detailed(
            type_=type_,
            client=client,
            body=body,
        )
    ).parsed
