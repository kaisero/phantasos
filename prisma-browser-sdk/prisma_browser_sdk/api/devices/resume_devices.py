from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.device_resume_response import DeviceResumeResponse
from ...models.device_status_change_request import DeviceStatusChangeRequest
from ...models.resume_devices_response_400 import ResumeDevicesResponse400
from ...models.resume_devices_response_404 import ResumeDevicesResponse404
from ...types import Response


def _get_kwargs(
    *,
    body: DeviceStatusChangeRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/seb-api/v1/devices/resume",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404 | None:
    if response.status_code == 200:
        response_200 = DeviceResumeResponse.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ResumeDevicesResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ResumeDevicesResponse404.from_dict(response.json())

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
) -> Response[ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404]:
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
) -> Response[ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404]:
    """Resume suspended devices

     Resume one or more suspended devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404]
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
) -> ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404 | None:
    """Resume suspended devices

     Resume one or more suspended devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: DeviceStatusChangeRequest,
) -> Response[ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404]:
    """Resume suspended devices

     Resume one or more suspended devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404]
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
) -> ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404 | None:
    """Resume suspended devices

     Resume one or more suspended devices by changing their status to active

    Args:
        body (DeviceStatusChangeRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceResumeResponse | ResumeDevicesResponse400 | ResumeDevicesResponse404
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
