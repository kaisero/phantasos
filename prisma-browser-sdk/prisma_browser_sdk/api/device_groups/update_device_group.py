from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.device_group_request import DeviceGroupRequest
from ...models.update_device_group_response_200 import UpdateDeviceGroupResponse200
from ...models.update_device_group_response_400 import UpdateDeviceGroupResponse400
from ...types import Response


def _get_kwargs(
    device_group_id: str,
    *,
    body: DeviceGroupRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/seb-api/v1/device-groups/{device_group_id}".format(
            device_group_id=quote(str(device_group_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400 | None:
    if response.status_code == 200:
        response_200 = UpdateDeviceGroupResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = UpdateDeviceGroupResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ApiError.from_dict(response.json())

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
) -> Response[ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> Response[ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400]:
    """Replace entire device group

     Replaces the entire device group - missing attributes are disabled, provided attributes are set as
    specified.

    Args:
        device_group_id (str):
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400]
    """

    kwargs = _get_kwargs(
        device_group_id=device_group_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400 | None:
    """Replace entire device group

     Replaces the entire device group - missing attributes are disabled, provided attributes are set as
    specified.

    Args:
        device_group_id (str):
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400
    """

    return sync_detailed(
        device_group_id=device_group_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> Response[ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400]:
    """Replace entire device group

     Replaces the entire device group - missing attributes are disabled, provided attributes are set as
    specified.

    Args:
        device_group_id (str):
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400]
    """

    kwargs = _get_kwargs(
        device_group_id=device_group_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: DeviceGroupRequest,
) -> ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400 | None:
    """Replace entire device group

     Replaces the entire device group - missing attributes are disabled, provided attributes are set as
    specified.

    Args:
        device_group_id (str):
        body (DeviceGroupRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | UpdateDeviceGroupResponse200 | UpdateDeviceGroupResponse400
    """

    return (
        await asyncio_detailed(
            device_group_id=device_group_id,
            client=client,
            body=body,
        )
    ).parsed
