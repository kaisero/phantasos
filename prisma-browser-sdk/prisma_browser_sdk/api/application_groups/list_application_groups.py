from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.api_error import ApiError
from ...models.list_application_groups_response_200 import ListApplicationGroupsResponse200
from ...models.list_application_groups_response_400 import ListApplicationGroupsResponse400
from ...models.list_application_groups_sort import ListApplicationGroupsSort
from ...models.order import Order
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    configuration_version: str | Unset = "draft",
    name: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["configurationVersion"] = configuration_version

    params["name"] = name

    params["cursor"] = cursor

    params["limit"] = limit

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
        "url": "/seb-api/v1/application-groups",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400 | None:
    if response.status_code == 200:
        response_200 = ListApplicationGroupsResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ListApplicationGroupsResponse400.from_dict(response.json())

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
) -> Response[ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    name: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400]:
    """Returns a list of application groups

     Fetches all application groups with support for name-based filtering and sorting.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        name (str | Unset):
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationGroupsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400]
    """

    kwargs = _get_kwargs(
        configuration_version=configuration_version,
        name=name,
        cursor=cursor,
        limit=limit,
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
    configuration_version: str | Unset = "draft",
    name: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400 | None:
    """Returns a list of application groups

     Fetches all application groups with support for name-based filtering and sorting.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        name (str | Unset):
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationGroupsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400
    """

    return sync_detailed(
        client=client,
        configuration_version=configuration_version,
        name=name,
        cursor=cursor,
        limit=limit,
        sort=sort,
        order=order,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    name: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> Response[ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400]:
    """Returns a list of application groups

     Fetches all application groups with support for name-based filtering and sorting.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        name (str | Unset):
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationGroupsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400]
    """

    kwargs = _get_kwargs(
        configuration_version=configuration_version,
        name=name,
        cursor=cursor,
        limit=limit,
        sort=sort,
        order=order,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    configuration_version: str | Unset = "draft",
    name: str | Unset = UNSET,
    cursor: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    sort: ListApplicationGroupsSort | Unset = UNSET,
    order: Order | Unset = UNSET,
) -> ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400 | None:
    """Returns a list of application groups

     Fetches all application groups with support for name-based filtering and sorting.

    Args:
        configuration_version (str | Unset):  Default: 'draft'.
        name (str | Unset):
        cursor (str | Unset):
        limit (int | Unset):
        sort (ListApplicationGroupsSort | Unset):
        order (Order | Unset): The sort order

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ApiError | ListApplicationGroupsResponse200 | ListApplicationGroupsResponse400
    """

    return (
        await asyncio_detailed(
            client=client,
            configuration_version=configuration_version,
            name=name,
            cursor=cursor,
            limit=limit,
            sort=sort,
            order=order,
        )
    ).parsed
