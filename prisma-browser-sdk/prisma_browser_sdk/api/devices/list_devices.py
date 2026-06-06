import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.list_devices_response_200 import ListDevicesResponse200
from ...models.list_devices_sort import ListDevicesSort
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = UNSET,
    device_hostname: str | Unset = UNSET,
    user_name: str | Unset = UNSET,
    device_os_type: str | Unset = UNSET,
    device_first_seen_gte: datetime.datetime | Unset = UNSET,
    device_last_seen_lte: datetime.datetime | Unset = UNSET,
    device_last_seen_gte: datetime.datetime | Unset = UNSET,
    device_type: str | Unset = UNSET,
    device_firewall_status: str | Unset = UNSET,
    device_screen_lock_status: str | Unset = UNSET,
    device_disk_encryption_status: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDevicesSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["limit"] = limit

    params["device.hostname"] = device_hostname

    params["user.name"] = user_name

    params["device.os_type"] = device_os_type

    json_device_first_seen_gte: str | Unset = UNSET
    if not isinstance(device_first_seen_gte, Unset):
        json_device_first_seen_gte = device_first_seen_gte.isoformat()
    params["device.first_seen_gte"] = json_device_first_seen_gte

    json_device_last_seen_lte: str | Unset = UNSET
    if not isinstance(device_last_seen_lte, Unset):
        json_device_last_seen_lte = device_last_seen_lte.isoformat()
    params["device.last_seen_lte"] = json_device_last_seen_lte

    json_device_last_seen_gte: str | Unset = UNSET
    if not isinstance(device_last_seen_gte, Unset):
        json_device_last_seen_gte = device_last_seen_gte.isoformat()
    params["device.last_seen_gte"] = json_device_last_seen_gte

    params["device.type"] = device_type

    params["device.firewall_status"] = device_firewall_status

    params["device.screen_lock_status"] = device_screen_lock_status

    params["device.disk_encryption_status"] = device_disk_encryption_status

    params["cursor"] = cursor

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    json_order: str | Unset = UNSET
    if not isinstance(order, Unset):
        json_order = order.value

    params["order"] = json_order

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/devices",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListDevicesResponse200 | None:
    if response.status_code == 200:
        response_200 = ListDevicesResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ApiError.from_dict(response.json())

        return response_400

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | ListDevicesResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_hostname: str | Unset = UNSET,
    user_name: str | Unset = UNSET,
    device_os_type: str | Unset = UNSET,
    device_first_seen_gte: datetime.datetime | Unset = UNSET,
    device_last_seen_lte: datetime.datetime | Unset = UNSET,
    device_last_seen_gte: datetime.datetime | Unset = UNSET,
    device_type: str | Unset = UNSET,
    device_firewall_status: str | Unset = UNSET,
    device_screen_lock_status: str | Unset = UNSET,
    device_disk_encryption_status: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDevicesSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListDevicesResponse200]:
    """Returns a list of devices

    Args:
        limit (int | Unset):
        device_hostname (str | Unset):
        user_name (str | Unset):
        device_os_type (str | Unset):
        device_first_seen_gte (datetime.datetime | Unset):
        device_last_seen_lte (datetime.datetime | Unset):
        device_last_seen_gte (datetime.datetime | Unset):
        device_type (str | Unset):
        device_firewall_status (str | Unset):
        device_screen_lock_status (str | Unset):
        device_disk_encryption_status (str | Unset):
        cursor (str | Unset):
        sort (ListDevicesSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListDevicesResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        device_hostname=device_hostname,
        user_name=user_name,
        device_os_type=device_os_type,
        device_first_seen_gte=device_first_seen_gte,
        device_last_seen_lte=device_last_seen_lte,
        device_last_seen_gte=device_last_seen_gte,
        device_type=device_type,
        device_firewall_status=device_firewall_status,
        device_screen_lock_status=device_screen_lock_status,
        device_disk_encryption_status=device_disk_encryption_status,
        cursor=cursor,
        sort=sort,
        order=order,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_hostname: str | Unset = UNSET,
    user_name: str | Unset = UNSET,
    device_os_type: str | Unset = UNSET,
    device_first_seen_gte: datetime.datetime | Unset = UNSET,
    device_last_seen_lte: datetime.datetime | Unset = UNSET,
    device_last_seen_gte: datetime.datetime | Unset = UNSET,
    device_type: str | Unset = UNSET,
    device_firewall_status: str | Unset = UNSET,
    device_screen_lock_status: str | Unset = UNSET,
    device_disk_encryption_status: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDevicesSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListDevicesResponse200 | None:
    """Returns a list of devices

    Args:
        limit (int | Unset):
        device_hostname (str | Unset):
        user_name (str | Unset):
        device_os_type (str | Unset):
        device_first_seen_gte (datetime.datetime | Unset):
        device_last_seen_lte (datetime.datetime | Unset):
        device_last_seen_gte (datetime.datetime | Unset):
        device_type (str | Unset):
        device_firewall_status (str | Unset):
        device_screen_lock_status (str | Unset):
        device_disk_encryption_status (str | Unset):
        cursor (str | Unset):
        sort (ListDevicesSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListDevicesResponse200
    """

    return sync_detailed(
        client=client,
        limit=limit,
        device_hostname=device_hostname,
        user_name=user_name,
        device_os_type=device_os_type,
        device_first_seen_gte=device_first_seen_gte,
        device_last_seen_lte=device_last_seen_lte,
        device_last_seen_gte=device_last_seen_gte,
        device_type=device_type,
        device_firewall_status=device_firewall_status,
        device_screen_lock_status=device_screen_lock_status,
        device_disk_encryption_status=device_disk_encryption_status,
        cursor=cursor,
        sort=sort,
        order=order,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_hostname: str | Unset = UNSET,
    user_name: str | Unset = UNSET,
    device_os_type: str | Unset = UNSET,
    device_first_seen_gte: datetime.datetime | Unset = UNSET,
    device_last_seen_lte: datetime.datetime | Unset = UNSET,
    device_last_seen_gte: datetime.datetime | Unset = UNSET,
    device_type: str | Unset = UNSET,
    device_firewall_status: str | Unset = UNSET,
    device_screen_lock_status: str | Unset = UNSET,
    device_disk_encryption_status: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDevicesSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListDevicesResponse200]:
    """Returns a list of devices

    Args:
        limit (int | Unset):
        device_hostname (str | Unset):
        user_name (str | Unset):
        device_os_type (str | Unset):
        device_first_seen_gte (datetime.datetime | Unset):
        device_last_seen_lte (datetime.datetime | Unset):
        device_last_seen_gte (datetime.datetime | Unset):
        device_type (str | Unset):
        device_firewall_status (str | Unset):
        device_screen_lock_status (str | Unset):
        device_disk_encryption_status (str | Unset):
        cursor (str | Unset):
        sort (ListDevicesSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListDevicesResponse200]
    """

    kwargs = _get_kwargs(
        limit=limit,
        device_hostname=device_hostname,
        user_name=user_name,
        device_os_type=device_os_type,
        device_first_seen_gte=device_first_seen_gte,
        device_last_seen_lte=device_last_seen_lte,
        device_last_seen_gte=device_last_seen_gte,
        device_type=device_type,
        device_firewall_status=device_firewall_status,
        device_screen_lock_status=device_screen_lock_status,
        device_disk_encryption_status=device_disk_encryption_status,
        cursor=cursor,
        sort=sort,
        order=order,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_hostname: str | Unset = UNSET,
    user_name: str | Unset = UNSET,
    device_os_type: str | Unset = UNSET,
    device_first_seen_gte: datetime.datetime | Unset = UNSET,
    device_last_seen_lte: datetime.datetime | Unset = UNSET,
    device_last_seen_gte: datetime.datetime | Unset = UNSET,
    device_type: str | Unset = UNSET,
    device_firewall_status: str | Unset = UNSET,
    device_screen_lock_status: str | Unset = UNSET,
    device_disk_encryption_status: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDevicesSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListDevicesResponse200 | None:
    """Returns a list of devices

    Args:
        limit (int | Unset):
        device_hostname (str | Unset):
        user_name (str | Unset):
        device_os_type (str | Unset):
        device_first_seen_gte (datetime.datetime | Unset):
        device_last_seen_lte (datetime.datetime | Unset):
        device_last_seen_gte (datetime.datetime | Unset):
        device_type (str | Unset):
        device_firewall_status (str | Unset):
        device_screen_lock_status (str | Unset):
        device_disk_encryption_status (str | Unset):
        cursor (str | Unset):
        sort (ListDevicesSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListDevicesResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
            device_hostname=device_hostname,
            user_name=user_name,
            device_os_type=device_os_type,
            device_first_seen_gte=device_first_seen_gte,
            device_last_seen_lte=device_last_seen_lte,
            device_last_seen_gte=device_last_seen_gte,
            device_type=device_type,
            device_firewall_status=device_firewall_status,
            device_screen_lock_status=device_screen_lock_status,
            device_disk_encryption_status=device_disk_encryption_status,
            cursor=cursor,
            sort=sort,
            order=order,
        )
    ).parsed
