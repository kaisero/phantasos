from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_application_response_201 import CreateApplicationResponse201
from ...models.create_application_response_400 import CreateApplicationResponse400
from ...models.create_application_response_409 import CreateApplicationResponse409
from ...models.create_application_type import CreateApplicationType
from ...models.custom_application_input import CustomApplicationInput
from ...models.local_desktop_application_input import LocalDesktopApplicationInput
from ...models.non_web_application_input import NonWebApplicationInput
from ...models.private_application_input import PrivateApplicationInput
from ...types import Response


def _get_kwargs(
    type_: CreateApplicationType,
    *,
    body: CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/applications/type/{type_}".format(
            type_=quote(str(type_), safe=""),
        ),
    }

    if isinstance(body, CustomApplicationInput):
        _kwargs["json"] = body.to_dict()
    elif isinstance(body, PrivateApplicationInput):
        _kwargs["json"] = body.to_dict()
    elif isinstance(body, NonWebApplicationInput):
        _kwargs["json"] = body.to_dict()
    else:
        _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409 | None:
    if response.status_code == 201:
        response_201 = CreateApplicationResponse201.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = CreateApplicationResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = cast(Any, None)
        return response_403

    if response.status_code == 409:
        response_409 = CreateApplicationResponse409.from_dict(response.json())

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
) -> Response[Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    type_: CreateApplicationType,
    *,
    client: AuthenticatedClient | Client,
    body: CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput,
) -> Response[Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409]:
    """Creates an application

     Adds a new application of the specified type to the management console.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (CreateApplicationType):
        body (CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput |
            PrivateApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409]
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
    type_: CreateApplicationType,
    *,
    client: AuthenticatedClient | Client,
    body: CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput,
) -> Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409 | None:
    """Creates an application

     Adds a new application of the specified type to the management console.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (CreateApplicationType):
        body (CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput |
            PrivateApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409
    """

    return sync_detailed(
        type_=type_,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    type_: CreateApplicationType,
    *,
    client: AuthenticatedClient | Client,
    body: CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput,
) -> Response[Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409]:
    """Creates an application

     Adds a new application of the specified type to the management console.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (CreateApplicationType):
        body (CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput |
            PrivateApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409]
    """

    kwargs = _get_kwargs(
        type_=type_,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    type_: CreateApplicationType,
    *,
    client: AuthenticatedClient | Client,
    body: CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput | PrivateApplicationInput,
) -> Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409 | None:
    """Creates an application

     Adds a new application of the specified type to the management console.

    **URL Limit:** For custom, private, and non-web applications, there is a tenant-wide limit of 15,000
    URLs combined. Exceeding this limit returns a 400 Bad Request error.

    Args:
        type_ (CreateApplicationType):
        body (CustomApplicationInput | LocalDesktopApplicationInput | NonWebApplicationInput |
            PrivateApplicationInput):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | CreateApplicationResponse201 | CreateApplicationResponse400 | CreateApplicationResponse409
    """

    return (
        await asyncio_detailed(
            type_=type_,
            client=client,
            body=body,
        )
    ).parsed
