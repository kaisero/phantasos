import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.device_group_platform import DeviceGroupPlatform
from ...models.list_device_groups_response_200 import ListDeviceGroupsResponse200
from ...models.list_device_groups_response_400 import ListDeviceGroupsResponse400
from ...models.list_device_groups_sort import ListDeviceGroupsSort
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    limit: int | Unset = UNSET,
    device_group_name: str | Unset = UNSET,
    device_group_platform: DeviceGroupPlatform | Unset = UNSET,
    device_group_created_at_gte: datetime.datetime | Unset = UNSET,
    device_group_created_at_lte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_gte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_lte: datetime.datetime | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDeviceGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["limit"] = limit

    params["deviceGroup.name"] = device_group_name

    json_device_group_platform: str | Unset = UNSET
    if not isinstance(device_group_platform, Unset):
        json_device_group_platform = device_group_platform.value

    params["deviceGroup.platform"] = json_device_group_platform

    json_device_group_created_at_gte: str | Unset = UNSET
    if not isinstance(device_group_created_at_gte, Unset):
        json_device_group_created_at_gte = device_group_created_at_gte.isoformat()
    params["deviceGroup.created_at_gte"] = json_device_group_created_at_gte

    json_device_group_created_at_lte: str | Unset = UNSET
    if not isinstance(device_group_created_at_lte, Unset):
        json_device_group_created_at_lte = device_group_created_at_lte.isoformat()
    params["deviceGroup.created_at_lte"] = json_device_group_created_at_lte

    json_device_group_updated_at_gte: str | Unset = UNSET
    if not isinstance(device_group_updated_at_gte, Unset):
        json_device_group_updated_at_gte = device_group_updated_at_gte.isoformat()
    params["deviceGroup.updated_at_gte"] = json_device_group_updated_at_gte

    json_device_group_updated_at_lte: str | Unset = UNSET
    if not isinstance(device_group_updated_at_lte, Unset):
        json_device_group_updated_at_lte = device_group_updated_at_lte.isoformat()
    params["deviceGroup.updated_at_lte"] = json_device_group_updated_at_lte

    params["cursor"] = cursor

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    json_order: str | Unset = UNSET
    if not isinstance(order, Unset):
        json_order = order.value

    params["order"] = json_order

    params["configurationVersion"] = configuration_version

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/seb-api/v1/device-groups",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400 | None:
    if response.status_code == 200:
        response_200 = ListDeviceGroupsResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ListDeviceGroupsResponse400.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ApiError.from_dict(response.json())

        return response_403

    if response.status_code == 500:
        response_500 = ApiError.from_dict(response.json())

        return response_500

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400]:
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
    device_group_name: str | Unset = UNSET,
    device_group_platform: DeviceGroupPlatform | Unset = UNSET,
    device_group_created_at_gte: datetime.datetime | Unset = UNSET,
    device_group_created_at_lte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_gte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_lte: datetime.datetime | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDeviceGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Response[ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400]:
    """Returns a list of device groups

    Args:
        limit (int | Unset):
        device_group_name (str | Unset):
        device_group_platform (DeviceGroupPlatform | Unset): Device group platform
        device_group_created_at_gte (datetime.datetime | Unset):
        device_group_created_at_lte (datetime.datetime | Unset):
        device_group_updated_at_gte (datetime.datetime | Unset):
        device_group_updated_at_lte (datetime.datetime | Unset):
        cursor (str | Unset):
        sort (ListDeviceGroupsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400]
    """

    kwargs = _get_kwargs(
        limit=limit,
        device_group_name=device_group_name,
        device_group_platform=device_group_platform,
        device_group_created_at_gte=device_group_created_at_gte,
        device_group_created_at_lte=device_group_created_at_lte,
        device_group_updated_at_gte=device_group_updated_at_gte,
        device_group_updated_at_lte=device_group_updated_at_lte,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_group_name: str | Unset = UNSET,
    device_group_platform: DeviceGroupPlatform | Unset = UNSET,
    device_group_created_at_gte: datetime.datetime | Unset = UNSET,
    device_group_created_at_lte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_gte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_lte: datetime.datetime | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDeviceGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400 | None:
    """Returns a list of device groups

    Args:
        limit (int | Unset):
        device_group_name (str | Unset):
        device_group_platform (DeviceGroupPlatform | Unset): Device group platform
        device_group_created_at_gte (datetime.datetime | Unset):
        device_group_created_at_lte (datetime.datetime | Unset):
        device_group_updated_at_gte (datetime.datetime | Unset):
        device_group_updated_at_lte (datetime.datetime | Unset):
        cursor (str | Unset):
        sort (ListDeviceGroupsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400
    """

    return sync_detailed(
        client=client,
        limit=limit,
        device_group_name=device_group_name,
        device_group_platform=device_group_platform,
        device_group_created_at_gte=device_group_created_at_gte,
        device_group_created_at_lte=device_group_created_at_lte,
        device_group_updated_at_gte=device_group_updated_at_gte,
        device_group_updated_at_lte=device_group_updated_at_lte,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_group_name: str | Unset = UNSET,
    device_group_platform: DeviceGroupPlatform | Unset = UNSET,
    device_group_created_at_gte: datetime.datetime | Unset = UNSET,
    device_group_created_at_lte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_gte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_lte: datetime.datetime | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDeviceGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> Response[ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400]:
    """Returns a list of device groups

    Args:
        limit (int | Unset):
        device_group_name (str | Unset):
        device_group_platform (DeviceGroupPlatform | Unset): Device group platform
        device_group_created_at_gte (datetime.datetime | Unset):
        device_group_created_at_lte (datetime.datetime | Unset):
        device_group_updated_at_gte (datetime.datetime | Unset):
        device_group_updated_at_lte (datetime.datetime | Unset):
        cursor (str | Unset):
        sort (ListDeviceGroupsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400]
    """

    kwargs = _get_kwargs(
        limit=limit,
        device_group_name=device_group_name,
        device_group_platform=device_group_platform,
        device_group_created_at_gte=device_group_created_at_gte,
        device_group_created_at_lte=device_group_created_at_lte,
        device_group_updated_at_gte=device_group_updated_at_gte,
        device_group_updated_at_lte=device_group_updated_at_lte,
        cursor=cursor,
        sort=sort,
        order=order,
        configuration_version=configuration_version,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    limit: int | Unset = UNSET,
    device_group_name: str | Unset = UNSET,
    device_group_platform: DeviceGroupPlatform | Unset = UNSET,
    device_group_created_at_gte: datetime.datetime | Unset = UNSET,
    device_group_created_at_lte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_gte: datetime.datetime | Unset = UNSET,
    device_group_updated_at_lte: datetime.datetime | Unset = UNSET,
    cursor: str | Unset = UNSET,
    sort: ListDeviceGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
    configuration_version: str | Unset = "draft",
) -> ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400 | None:
    """Returns a list of device groups

    Args:
        limit (int | Unset):
        device_group_name (str | Unset):
        device_group_platform (DeviceGroupPlatform | Unset): Device group platform
        device_group_created_at_gte (datetime.datetime | Unset):
        device_group_created_at_lte (datetime.datetime | Unset):
        device_group_updated_at_gte (datetime.datetime | Unset):
        device_group_updated_at_lte (datetime.datetime | Unset):
        cursor (str | Unset):
        sort (ListDeviceGroupsSort | Unset):
        order (Order | Unset): The sort order
        configuration_version (str | Unset):  Default: 'draft'.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListDeviceGroupsResponse200 | ListDeviceGroupsResponse400
    """

    return (
        await asyncio_detailed(
            client=client,
            limit=limit,
            device_group_name=device_group_name,
            device_group_platform=device_group_platform,
            device_group_created_at_gte=device_group_created_at_gte,
            device_group_created_at_lte=device_group_created_at_lte,
            device_group_updated_at_gte=device_group_updated_at_gte,
            device_group_updated_at_lte=device_group_updated_at_lte,
            cursor=cursor,
            sort=sort,
            order=order,
            configuration_version=configuration_version,
        )
    ).parsed
