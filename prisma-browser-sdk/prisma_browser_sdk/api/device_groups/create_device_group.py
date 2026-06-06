from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.create_device_group_response_201 import CreateDeviceGroupResponse201
from ...models.create_device_group_response_400 import CreateDeviceGroupResponse400
from ...models.create_device_group_response_409 import CreateDeviceGroupResponse409
from ...models.device_group_request import DeviceGroupRequest
from ...types import Response


def _get_kwargs(
    *,
    body: DeviceGroupRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/device-groups",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409 | None:
    if response.status_code == 201:
        response_201 = CreateDeviceGroupResponse201.from_dict(response.json())

        return response_201

    if response.status_code == 400:
        response_400 = CreateDeviceGroupResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 409:
        response_409 = CreateDeviceGroupResponse409.from_dict(response.json())

        return response_409

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> Response[ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409]:
    """Create a new device group

    Args:
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409 | None:
    """Create a new device group

    Args:
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> Response[ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409]:
    """Create a new device group

    Args:
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409 | None:
    """Create a new device group

    Args:
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | CreateDeviceGroupResponse201 | CreateDeviceGroupResponse400 | CreateDeviceGroupResponse409
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
