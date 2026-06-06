from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.device_group import DeviceGroup
from ...models.get_device_group_by_id_response_400 import GetDeviceGroupByIDResponse400
from ...types import UNSET, Response, Unset


def _get_kwargs(
    device_group_id: str,
    *,
    configuration_version: str | Unset = "draft",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["configurationVersion"] = configuration_version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/device-groups/{device_group_id}".format(
            device_group_id=quote(str(device_group_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | DeviceGroup | GetDeviceGroupByIDResponse400 | None:
    if response.status_code == 200:
        response_200 = DeviceGroup.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = GetDeviceGroupByIDResponse400.from_dict(response.json())

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
) -> Response[ApiError | DeviceGroup | GetDeviceGroupByIDResponse400]:
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
    configuration_version: str | Unset = "draft",
) -> Response[ApiError | DeviceGroup | GetDeviceGroupByIDResponse400]:
    """Returns a device group by ID

    Args:
        device_group_id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceGroup | GetDeviceGroupByIDResponse400]
    """

    kwargs = _get_kwargs(
        device_group_id=device_group_id,
        configuration_version=configuration_version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> ApiError | DeviceGroup | GetDeviceGroupByIDResponse400 | None:
    """Returns a device group by ID

    Args:
        device_group_id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceGroup | GetDeviceGroupByIDResponse400
    """

    return sync_detailed(
        device_group_id=device_group_id,
        client=client,
        configuration_version=configuration_version,
    ).parsed


async def asyncio_detailed(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> Response[ApiError | DeviceGroup | GetDeviceGroupByIDResponse400]:
    """Returns a device group by ID

    Args:
        device_group_id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | DeviceGroup | GetDeviceGroupByIDResponse400]
    """

    kwargs = _get_kwargs(
        device_group_id=device_group_id,
        configuration_version=configuration_version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    device_group_id: str,
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
) -> ApiError | DeviceGroup | GetDeviceGroupByIDResponse400 | None:
    """Returns a device group by ID

    Args:
        device_group_id (str):
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | DeviceGroup | GetDeviceGroupByIDResponse400
    """

    return (
        await asyncio_detailed(
            device_group_id=device_group_id,
            client=client,
            configuration_version=configuration_version,
        )
    ).parsed
