from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.device_restore_response import DeviceRestoreResponse
from ...models.device_status_change_request import DeviceStatusChangeRequest
from ...models.restore_devices_response_400 import RestoreDevicesResponse400
from ...models.restore_devices_response_404 import RestoreDevicesResponse404
from ...types import Response


def _get_kwargs(
    *,
    body: DeviceStatusChangeRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/devices/restore",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404 | None:
    if response.status_code == 200:
        response_200 = DeviceRestoreResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = RestoreDevicesResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = RestoreDevicesResponse404.from_dict(response.json())

        return response_404

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceStatusChangeRequest,
) -> Response[ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404]:
    """Restore archived devices

     Restore one or more archived devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404]
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
    body: DeviceStatusChangeRequest,
) -> ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404 | None:
    """Restore archived devices

     Restore one or more archived devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceStatusChangeRequest,
) -> Response[ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404]:
    """Restore archived devices

     Restore one or more archived devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceStatusChangeRequest,
) -> ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404 | None:
    """Restore archived devices

     Restore one or more archived devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceRestoreResponse | RestoreDevicesResponse400 | RestoreDevicesResponse404
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
